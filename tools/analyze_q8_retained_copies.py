#!/usr/bin/env python3
"""Replay real swaps: bounded retained RAM copies, with unchanged GPU placement.

These are potential D2H payload savings, NOT throughput predictions. The FIFO
policy retains the most recently promoted experts. The oracle knows future
evictions and is only an optimistic bound for this unchanged sequence of swaps.
Existing temporary exchange buffers remain required in addition to this budget.
"""
from collections import OrderedDict, defaultdict, deque
from pathlib import Path
import argparse
import hashlib
import json

PREFIX = 'strata exchange trace: '


def load_batches(text):
    batches, known = [], {}
    expected, geometry = 0, None
    for line in text.splitlines():
        if PREFIX not in line:
            continue
        row = json.loads(line.split(PREFIX, 1)[1])
        shape = (row['experts'], row['per_layer'], row['bytes'])
        if row['schema'] != 1 or min(shape) <= 0:
            raise ValueError('Unsupported trace geometry')
        if geometry is not None and geometry != shape:
            raise ValueError('Geometry changed within one engine trace')
        geometry = shape
        pairs = row['pairs']
        if row['first'] != expected or row['applied'] != len(pairs) or not pairs:
            raise ValueError('Missing, repeated, or partially applied exchange batch')
        ids = [e for pair in pairs for e in pair]
        if len(ids) != len(set(ids)):
            raise ValueError('An expert participates twice within a batch')
        for incoming, outgoing in pairs:
            if not (0 <= incoming < shape[0] and 0 <= outgoing < shape[0]):
                raise ValueError('Expert ID outside geometry')
            if incoming // shape[1] != outgoing // shape[1]:
                raise ValueError('Exchange crosses layers')
            if known.get(incoming, 'ram') != 'ram' or known.get(outgoing, 'gpu') != 'gpu':
                raise ValueError('Ownership sequence is inconsistent')
        for incoming, outgoing in pairs:
            known[incoming], known[outgoing] = 'gpu', 'ram'
        batches.append(row)
        expected += len(pairs)
    if not batches:
        raise ValueError('No exchange trace found')
    return batches


def replay(batches, slots, policy='fifo'):
    if slots < 0 or policy not in ('fifo', 'oracle'):
        raise ValueError('Invalid capacity or policy')
    copies = OrderedDict()
    future = defaultdict(deque)
    for index, batch in enumerate(batches):
        for _, outgoing in batch['pairs']:
            future[outgoing].append(index)
    total = saved = peak = 0
    saved_by_batch = []
    for index, batch in enumerate(batches):
        hits = 0
        # Consume every outgoing copy before selecting victims. Copies needed
        # later in THIS batch cannot be discarded by an earlier incoming expert.
        for _, outgoing in batch['pairs']:
            future[outgoing].popleft()
            if outgoing in copies:
                del copies[outgoing]
                hits += 1
        for incoming, _ in batch['pairs']:
            if incoming in copies:
                raise ValueError('Incoming expert was already a GPU shadow')
            copies[incoming] = None
        if policy == 'fifo':
            while len(copies) > slots:
                copies.popitem(last=False)
        elif len(copies) > slots:
            keep = sorted(copies, key=lambda e: (future[e][0] if future[e] else float('inf'), e))[:slots]
            copies = OrderedDict.fromkeys(keep)
        peak = max(peak, len(copies))
        saved += hits * batch['bytes']
        total += len(batch['pairs']) * batch['bytes']
        saved_by_batch.append(hits)
    return dict(policy=policy, slots=slots, peak_retained_slots=peak,
                retained_ram_bytes=slots * batches[0]['bytes'],
                baseline_d2h_payload_bytes=total, avoided_d2h_payload_bytes=saved,
                avoided_d2h_fraction=saved / total if total else 0,
                avoided_experts_per_batch=saved_by_batch)


def analyze(path):
    raw = path.read_bytes()
    batches = load_batches(raw.decode('utf-8', errors='replace'))
    blob = batches[0]['bytes']
    capacities = [0, 0.25, 0.5, 1, 2, 4, 8]
    return dict(log=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                batches=len(batches), exchanges=sum(len(b['pairs']) for b in batches),
                expert_bytes=blob,
                limitation='Replay of unchanged placement; payload savings only, not measured speed. Oracle uses future information. Extra buffers and runtime overhead are not modeled.',
                projections=[replay(batches, int(gib * 2**30) // blob, policy)
                             for policy in ('fifo', 'oracle') for gib in capacities])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('logs', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'traces': [analyze(path) for path in args.logs]}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for trace in result['traces']:
        print(trace['log'], 'exchanges', trace['exchanges'])
        for p in trace['projections']:
            print(p['policy'], round(p['retained_ram_bytes'] / 2**30, 3),
                  'GiB:', round(100 * p['avoided_d2h_fraction'], 2), '% D2H payload avoided')


if __name__ == '__main__':
    main()
