#!/usr/bin/env python3
"""Replay the unchanged GPU cache and count CPU work with already cached weights.

This is placement opportunity, not predicted throughput. Redirecting work would
change arithmetic and require its own numerical/state/performance validation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

PREFIX = 'strata miss route trace: '
COUNTERS = re.compile(r'strata readonly miss cache: cumulative groups=(\d+) hits=(\d+) '
                     r'uploads=(\d+) bypasses=(\d+) avoided_upload_bytes=(\d+) uploaded_bytes=(\d+)')
TRAFFIC = re.compile(r'strata decode traffic: committed=(\d+) pcie_expert_groups=(\d+) '
                    r'uniform_blob_bytes=(\d+) logical_pcie_weight_bytes=(\d+)')
KEYS = ('gpu_groups', 'gpu_hits', 'gpu_uploads', 'gpu_bypasses',
        'cpu_groups', 'cpu_entries', 'cpu_cached_before_groups', 'cpu_cached_before_entries',
        'cpu_cached_surviving_groups', 'cpu_cached_surviving_entries')


class Replay:
    def __init__(self, ways, layers):
        if ways < 0 or ways > 16 or layers < 1:
            raise ValueError('Unsupported cache geometry')
        self.ways = ways
        self.banks = [dict(tags=[-1]*ways, ages=[0]*ways, clock=0) for _ in range(layers)]
        self.total = dict.fromkeys(KEYS, 0)
        self.by_layer = [dict.fromkeys(KEYS, 0) for _ in range(layers)]

    def add(self, row):
        bank = self.banks[row['layer']]
        before = set(bank['tags'])
        cpu = [(expert, count) for expert, kind, count in row['groups'] if kind == -1]
        gpu = [expert for expert, kind, count in row['groups'] if kind == 1]
        used = set()
        missing = []
        delta = dict.fromkeys(KEYS, 0)
        delta['gpu_groups'] = len(gpu)
        delta['cpu_groups'] = len(cpu)
        delta['cpu_entries'] = sum(count for _, count in cpu)
        # Match the kernel's two-phase reservation: every GPU hit is protected
        # before any miss chooses its victim, regardless of group order.
        for expert in gpu:
            if expert in bank['tags']:
                slot = bank['tags'].index(expert)
                used.add(slot)
                bank['clock'] += 1
                bank['ages'][slot] = bank['clock']
                delta['gpu_hits'] += 1
            else:
                missing.append(expert)
        for expert in missing:
            delta['gpu_uploads'] += 1
            available = [i for i in range(self.ways) if i not in used]
            if not available:
                delta['gpu_bypasses'] += 1
                continue
            empty = next((i for i in available if bank['tags'][i] < 0), None)
            slot = empty if empty is not None else min(available, key=lambda i: bank['ages'][i])
            used.add(slot)
            bank['clock'] += 1
            bank['tags'][slot] = expert
            bank['ages'][slot] = bank['clock']
        after = set(bank['tags'])
        for expert, count in cpu:
            if expert in before:
                delta['cpu_cached_before_groups'] += 1
                delta['cpu_cached_before_entries'] += count
                if expert in after:
                    delta['cpu_cached_surviving_groups'] += 1
                    delta['cpu_cached_surviving_entries'] += count
        for key, value in delta.items():
            self.total[key] += value
            self.by_layer[row['layer']][key] += value


def validate_row(row, sequence, shape):
    geometry = (row['layers'], row['per_layer'], row['bytes'])
    if row['schema'] != 1 or row['sequence'] != sequence or min(geometry) < 1:
        raise ValueError('Invalid geometry or missing/repeated trace row')
    if shape is not None and geometry != shape:
        raise ValueError('Trace geometry changed')
    if row['layer'] != sequence % row['layers']:
        raise ValueError('Missing, repeated or out-of-order layer')
    if not (1 <= row['tokens'] <= 16 and row['topk'] == 10):
        raise ValueError('Unexpected verification geometry')
    groups = row['groups']
    if not groups or any(len(g) != 3 for g in groups):
        raise ValueError('Malformed expert group')
    experts = [g[0] for g in groups]
    if len(experts) != len(set(experts)) or any(not 0 <= e < row['per_layer'] for e in experts):
        raise ValueError('Repeated or invalid expert')
    if any(kind not in (-1, 0, 1) or count < 1 or count > row['tokens'] for _, kind, count in groups):
        raise ValueError('Unsupported assignment or entry count')
    if sum(g[2] for g in groups) != row['tokens']*row['topk']:
        raise ValueError('Missing routed entries')
    return geometry


def analyze(path):
    raw = path.read_bytes()
    text = raw.decode('utf-8', errors='strict')
    enabled = re.findall(r'strata readonly miss cache: enabled, ways=(\d+) layers=(\d+) bytes=(\d+);', text)
    if len(enabled) != 1:
        raise ValueError('Expected one cache-enabled engine per trace')
    actual_ways, actual_layers, allocation = map(int, enabled[0])
    simulations = {ways: Replay(ways, actual_layers) for ways in (0, 4, 8, 16)}
    if actual_ways not in simulations:
        raise ValueError('Actual capacity not replayed')
    shape = None
    sequence = 0
    previous = {ways: dict(sim.total) for ways, sim in simulations.items()}
    requests = []
    traffic = None
    window_tokens = None
    for line in text.splitlines():
        if PREFIX in line:
            row = json.loads(line.split(PREFIX, 1)[1])
            shape = validate_row(row, sequence, shape)
            if row['layers'] != actual_layers:
                raise ValueError('Cache and trace layer counts differ')
            if row['layer'] == 0:
                window_tokens = row['tokens']
            if window_tokens != row['tokens']:
                raise ValueError('Token count changed within a window')
            for sim in simulations.values():
                sim.add(row)
            sequence += 1
        elif match := TRAFFIC.search(line):
            if traffic is not None:
                raise ValueError('Traffic record missing its cache counters')
            traffic = list(map(int, match.groups()))
        elif match := COUNTERS.search(line):
            if not shape or sequence % actual_layers or traffic is None:
                raise ValueError('Request boundary lacks complete trace/traffic')
            committed, gpu_groups, blob, logical = traffic
            observed = list(map(int, match.groups()))
            actual = simulations[actual_ways].total
            expected = [actual[k] for k in ('gpu_groups', 'gpu_hits', 'gpu_uploads', 'gpu_bypasses')]
            expected += [actual['gpu_hits']*shape[2], actual['gpu_uploads']*shape[2]]
            if observed != expected:
                raise ValueError(f'Cache replay differs from device counters: {expected} != {observed}')
            if blob != shape[2] or logical != gpu_groups*blob or gpu_groups != actual['gpu_groups']-previous[actual_ways]['gpu_groups']:
                raise ValueError('Trace differs from per-request logical PCIe accounting')
            if allocation != actual_ways*actual_layers*blob:
                raise ValueError('Actual cache allocation changed')
            projections = {}
            for ways, sim in simulations.items():
                delta = {key: sim.total[key]-previous[ways][key] for key in KEYS}
                delta['cpu_cached_before_fraction'] = delta['cpu_cached_before_groups']/delta['cpu_groups'] if delta['cpu_groups'] else 0
                delta['cpu_cached_surviving_fraction'] = delta['cpu_cached_surviving_groups']/delta['cpu_groups'] if delta['cpu_groups'] else 0
                projections[ways] = delta
                previous[ways] = dict(sim.total)
            requests.append(dict(index=len(requests), committed_tokens=committed,
                                 cumulative_rows=sequence, observed_cache_counters=observed,
                                 observed_logical_traffic=traffic, projections=projections))
            traffic = None
    if not requests or traffic is not None or sequence != requests[-1]['cumulative_rows']:
        raise ValueError('Trace is incomplete at the last request boundary')
    return dict(log=str(path), sha256=hashlib.sha256(raw).hexdigest(), rows=sequence,
                geometry=shape, actual_ways=actual_ways, device_counters_exact=True,
                requests=requests, totals={ways: sim.total for ways, sim in simulations.items()},
                per_layer={ways: sim.by_layer for ways, sim in simulations.items()},
                interpretation='Baseline CPU/GPU assignment replay only. Actual-capacity hit/upload/bypass '
                    'counts match device counters at every request boundary. CPU cached-before counts '
                    'weights present before current GPU fills; surviving counts also exclude weights those '
                    'fills evict. No CPU work was redirected. Other capacities are trace projections. '
                    'Neither count is a speed prediction: changed execution can alter arithmetic, routes, '
                    'cache replacement, contention and future speculative work. Trace timing is not throughput.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    results = [analyze(path) for path in args.logs]
    args.output.write_text(json.dumps(dict(traces=results), indent=2)+'\n')
    for result in results:
        print(result['log'], 'device counters exact:', result['device_counters_exact'])
        for request in result['requests']:
            actual = request['projections'][result['actual_ways']]
            print(request['index'], actual['cpu_groups'], 'CPU groups;',
                  actual['cpu_cached_before_groups'], 'cached before;',
                  actual['cpu_cached_surviving_groups'], 'survive current fills')


if __name__ == '__main__':
    main()
