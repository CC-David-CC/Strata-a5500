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
EXCHANGE_PREFIX = 'strata exchange trace: '
RAM_COUNTER = re.compile(r'strata serve: resident RAM: [0-9.]+ GiB of experts in RAM, (\d+) '
                         r'exchanged with the VRAM tier, (\d+) blob reads from the file')
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


class ExchangeOpportunity:
    """Observe immutable copies at committed exchange boundaries; never alter the cache."""
    def __init__(self, simulations):
        self.simulations = simulations
        self.known_ownership = {}
        self.count = 0
        self.batches = 0
        self.bytes = 0
        self.hits = dict.fromkeys(simulations, 0)
        self.hit_bytes = dict.fromkeys(simulations, 0)
        self.by_layer = {ways: [dict(promotions=0, cached_promotions=0)
                               for _ in sim.banks] for ways, sim in simulations.items()}

    def add(self, row, shape, sequence):
        if not shape or sequence % shape[0]:
            raise ValueError('Exchange was not between complete verification windows')
        layers, per_layer, blob = shape
        pairs = row['pairs']
        if (row['schema'] != 1 or row['first'] != self.count or row['experts'] != layers*per_layer
                or row['per_layer'] != per_layer or row['bytes'] != blob
                or not pairs or row['applied'] != len(pairs)
                or any(len(pair) != 2 for pair in pairs)):
            raise ValueError('Missing, repeated or malformed committed exchange')
        ids = [expert for pair in pairs for expert in pair]
        if len(ids) != len(set(ids)) or any(not 0 <= expert < layers*per_layer for expert in ids):
            raise ValueError('Repeated or invalid expert in exchange batch')
        for incoming, outgoing in pairs:
            if incoming // per_layer != outgoing // per_layer:
                raise ValueError('Exchange crosses layers')
            if (self.known_ownership.get(incoming, 'ram') != 'ram'
                    or self.known_ownership.get(outgoing, 'gpu') != 'gpu'):
                raise ValueError('Inconsistent primary ownership sequence')
        for incoming, outgoing in pairs:
            layer, expert = divmod(incoming, per_layer)
            for ways, sim in self.simulations.items():
                hit = expert in sim.banks[layer]['tags']
                self.hits[ways] += int(hit)
                self.hit_bytes[ways] += int(hit)*blob
                self.by_layer[ways][layer]['promotions'] += 1
                self.by_layer[ways][layer]['cached_promotions'] += int(hit)
            self.known_ownership[incoming], self.known_ownership[outgoing] = 'gpu', 'ram'
        self.count += len(pairs)
        self.bytes += len(pairs)*blob
        self.batches += 1

    def totals(self):
        return {ways: dict(committed_promotions=self.count, committed_upload_bytes=self.bytes,
                          cached_promotions=self.hits[ways], reusable_gpu_bytes=self.hit_bytes[ways],
                          cached_fraction=self.hits[ways]/self.count if self.count else 0)
                for ways in self.simulations}


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


def analyze(path, require_exchanges=False):
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
    exchange_enabled = require_exchanges or EXCHANGE_PREFIX in text
    exchanges = ExchangeOpportunity(simulations)
    previous_exchanges = exchanges.totals()
    exchange_footers = 0
    last_exchange_footer = 0
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
        elif EXCHANGE_PREFIX in line:
            row = json.loads(line.split(EXCHANGE_PREFIX, 1)[1])
            exchanges.add(row, shape, sequence)
        elif match := RAM_COUNTER.search(line):
            if not exchange_enabled:
                continue
            observed, file_reads = map(int, match.groups())
            if (not requests or 'exchange_opportunity' in requests[-1] or observed != exchanges.count
                    or file_reads != 0):
                raise ValueError('Committed exchange trace differs from request footer or lacks residency')
            current = exchanges.totals()
            deltas = {ways: {key: total[key]-previous_exchanges[ways][key]
                            for key in ('committed_promotions', 'committed_upload_bytes',
                                        'cached_promotions', 'reusable_gpu_bytes')}
                      for ways, total in current.items()}
            requests[-1]['exchange_opportunity'] = dict(observed_committed_exchanges=observed,
                                                        cumulative=current, since_prior_footer=deltas)
            previous_exchanges = current
            exchange_footers += 1
            last_exchange_footer = observed
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
    if exchange_enabled and (exchange_footers != len(requests) or last_exchange_footer != exchanges.count):
        raise ValueError('Exchange trace lacks its final request footer')
    return dict(log=str(path), sha256=hashlib.sha256(raw).hexdigest(), rows=sequence,
                geometry=shape, actual_ways=actual_ways, device_counters_exact=True,
                requests=requests, totals={ways: sim.total for ways, sim in simulations.items()},
                per_layer={ways: sim.by_layer for ways, sim in simulations.items()},
                promotion_opportunity=(dict(committed_counter_exact=True, batches=exchanges.batches,
                    totals=exchanges.totals(), per_layer=exchanges.by_layer,
                    interpretation='Only committed exchanges in this trace. Copies present in the secondary '
                      'GPU cache could potentially supply a device-to-device primary refill. No refill was '
                      'changed. Counts between request footers include delayed commits from a preceding '
                      'request; uncommitted final refills are excluded. Both source lifetime and full-byte '
                      'identity require separate validation before implementation; bytes are not speed gains.')
                    if exchange_enabled else None),
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
    parser.add_argument('--require-exchanges', action='store_true')
    args = parser.parse_args()
    results = [analyze(path, require_exchanges=args.require_exchanges) for path in args.logs]
    args.output.write_text(json.dumps(dict(traces=results), indent=2)+'\n')
    for result in results:
        print(result['log'], 'device counters exact:', result['device_counters_exact'])
        for request in result['requests']:
            actual = request['projections'][result['actual_ways']]
            print(request['index'], actual['cpu_groups'], 'CPU groups;',
                  actual['cpu_cached_before_groups'], 'cached before;',
                  actual['cpu_cached_surviving_groups'], 'survive current fills')
        if result['promotion_opportunity']:
            promotion = result['promotion_opportunity']['totals'][result['actual_ways']]
            print('Committed promotions:', promotion['committed_promotions'],
                  'already cached on GPU:', promotion['cached_promotions'])


if __name__ == '__main__':
    main()
