#!/usr/bin/env python3
"""Replay GPU-selected cache misses without changing the CPU/GPU split.

A second, read-only GPU cache could hold these weights across layers/windows.
Copies are immutable; eviction never needs to write them back. This is only a
payload-reuse projection, not a model speed measurement or implemented cache.
"""
from collections import OrderedDict
from pathlib import Path
import argparse
import hashlib
import json
import re

PREFIX = 'strata miss trace: '


def load_groups(text):
    records, geometry = [], None
    for line in text.splitlines():
        if PREFIX not in line:
            continue
        r = json.loads(line.split(PREFIX,1)[1])
        shape = (r['layers'],r['per_layer'],r['bytes'])
        if r['schema'] != 1 or r['sequence'] != len(records) or min(shape) <= 0:
            raise ValueError('Invalid trace geometry or missing/repeated group')
        if geometry is not None and geometry != shape:
            raise ValueError('Geometry changed')
        geometry = shape
        if not 0 <= r['layer'] < r['layers'] or not r['experts']:
            raise ValueError('Invalid layer or empty group')
        if len(set(r['experts'])) != len(r['experts']) or any(not 0 <= e < r['per_layer'] for e in r['experts']):
            raise ValueError('Expert ID invalid or repeated within group')
        records.append(r)
    if not records:
        raise ValueError('No miss trace records')
    return records


def replay(groups, capacity, per_layer=False):
    if capacity < 0:
        raise ValueError('Negative capacity')
    caches = {}
    total = saved = hits = requests = bypassed = 0
    for r in groups:
        cache = caches.setdefault(r['layer'] if per_layer else 0, OrderedDict())
        keys = [(r['layer'], e) for e in r['experts']]
        protected = set(keys)
        # Reserve every existing hit first. A miss earlier in the group cannot
        # overwrite a weight a later group member still needs.
        for key in keys:
            if key in cache:
                hits += 1; saved += r['bytes']; cache.move_to_end(key)
        for key in keys:
            if key in cache:
                continue
            if len(cache) >= capacity:
                victim = next((e for e in cache if e not in protected),None)
                if victim is None:
                    bypassed += 1
                    continue
                del cache[victim]
            cache[key] = None
        requests += len(keys)
        total += len(keys) * r['bytes']
    slots = capacity * groups[0]['layers'] if per_layer else capacity
    return dict(policy='per_layer_lru' if per_layer else 'global_lru', capacity=capacity,
                total_slots=slots, extra_gpu_bytes=slots*groups[0]['bytes'],
                requested_groups=requests, hit_groups=hits, bypassed_groups=bypassed,
                baseline_upload_payload_bytes=total, avoided_upload_payload_bytes=saved,
                avoided_upload_fraction=saved/total if total else 0)


def analyze(path):
    raw = path.read_bytes(); text=raw.decode('utf-8',errors='replace')
    groups = load_groups(text)
    total = sum(len(r['experts'])*r['bytes'] for r in groups)
    reported = sum(map(int,re.findall(r'logical_pcie_weight_bytes=(\d+)',text)))
    if total != reported:
        raise ValueError(f'Trace payload {total} differs from decode accounting {reported}')
    return dict(log=str(path),sha256=hashlib.sha256(raw).hexdigest(),groups=len(groups),
                logical_payload_verified=True,
                limit='Replay only. Same primary GPU placement and CPU/GPU split; extra GPU memory assumed available. Saved uploads do not directly predict speed. Original staging capacity remains additional.',
                projections=[replay(groups,c) for c in (0,32,64,128,192,256,384,512)] +
                            [replay(groups,c,True) for c in (1,2,4,8,16)])


def main():
    p=argparse.ArgumentParser();p.add_argument('logs',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();result=dict(traces=[analyze(f) for f in args.logs])
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    for t in result['traces']:
        print(t['log'])
        for r in t['projections']:
            print(r['policy'],r['capacity'],round(r['extra_gpu_bytes']/2**30,3),'GiB',round(r['avoided_upload_fraction']*100,2),'% uploads avoided')


if __name__=='__main__':main()
