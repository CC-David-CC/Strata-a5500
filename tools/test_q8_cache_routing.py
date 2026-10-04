#!/usr/bin/env python3
"""Exercise replay protection/eviction and independent per-request accounting."""
from pathlib import Path
import json
import tempfile
import unittest

from analyze_q8_cache_routing import EXCHANGE_PREFIX, ExchangeOpportunity, Replay, analyze


def row(sequence, groups):
    used = {g[0] for g in groups}
    groups = list(groups)
    expert = 100
    while len(groups) < 10:
        if expert not in used:
            groups.append([expert, 0, 1])
        expert += 1
    return dict(schema=1, sequence=sequence, layer=0, layers=1, per_layer=512,
                bytes=16, tokens=1, topk=10, groups=groups)


def fixture():
    rows = [row(0, [[e, 1, 1] for e in (1, 2, 3, 4)]),
            row(1, [[1, -1, 1], [5, 1, 1], [3, 1, 1]]),
            row(2, [[3, -1, 1], [2, 1, 1], [6, 1, 1]])]
    text = 'strata readonly miss cache: enabled, ways=4 layers=1 bytes=64;\n'
    for i, data in enumerate(rows):
        text += 'strata miss route trace: '+json.dumps(data)+'\n'
        if i == 1:
            text += ('strata decode traffic: committed=2 pcie_expert_groups=6 uniform_blob_bytes=16 logical_pcie_weight_bytes=96\n'
                     'strata readonly miss cache: cumulative groups=6 hits=1 uploads=5 bypasses=0 avoided_upload_bytes=16 uploaded_bytes=80\n')
        if i == 2:
            text += ('strata decode traffic: committed=1 pcie_expert_groups=2 uniform_blob_bytes=16 logical_pcie_weight_bytes=32\n'
                     'strata readonly miss cache: cumulative groups=8 hits=2 uploads=6 bypasses=0 avoided_upload_bytes=32 uploaded_bytes=96\n')
    return text


def exchange(first, pairs, layers=1):
    return dict(schema=1, first=first, experts=512*layers, per_layer=512,
                bytes=16, applied=len(pairs), pairs=pairs)


def promotion_fixture():
    lines = []
    for line in fixture().splitlines():
        if line.startswith('strata decode traffic: committed=2'):
            lines.append(EXCHANGE_PREFIX+json.dumps(exchange(0, [[5, 200], [10, 201]])))
        elif line.startswith('strata decode traffic: committed=1'):
            lines.append(EXCHANGE_PREFIX+json.dumps(exchange(2, [[6, 5]])))
        lines.append(line)
        if line.startswith('strata readonly miss cache: cumulative'):
            count = 2 if 'groups=6' in line else 3
            lines.append(f'strata serve: resident RAM: 1.00 GiB of experts in RAM, {count} exchanged '
                         'with the VRAM tier, 0 blob reads from the file')
    return '\n'.join(lines)+'\n'


class RoutingReplayTest(unittest.TestCase):
    def analyze_text(self, text, **options):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace.log'
            path.write_text(text)
            return analyze(path, **options)

    def test_later_gpu_hit_protected_and_cpu_eviction_visible(self):
        sim = Replay(2, 1)
        sim.add(row(0, [[1, 1, 1], [2, 1, 1]]))
        sim.add(row(1, [[1, -1, 1], [3, 1, 1], [2, 1, 1]]))
        self.assertEqual(set(sim.banks[0]['tags']), {2, 3})
        self.assertEqual(sim.total['gpu_hits'], 1)
        self.assertEqual(sim.total['cpu_cached_before_groups'], 1)
        self.assertEqual(sim.total['cpu_cached_surviving_groups'], 0)

    def test_zero_capacity_bypasses(self):
        sim = Replay(0, 1)
        sim.add(row(0, [[1, 1, 1], [2, 1, 1]]))
        sim.add(row(1, [[1, -1, 1], [2, 1, 1]]))
        self.assertEqual(sim.total['gpu_hits'], 0)
        self.assertEqual(sim.total['gpu_uploads'], 3)
        self.assertEqual(sim.total['gpu_bypasses'], 3)
        self.assertEqual(sim.total['cpu_cached_before_groups'], 0)

    def test_request_accounting_and_cpu_opportunity(self):
        result = self.analyze_text(fixture())
        self.assertTrue(result['device_counters_exact'])
        self.assertEqual(len(result['requests']), 2)
        self.assertEqual(result['totals'][4]['cpu_groups'], 2)
        self.assertEqual(result['totals'][4]['cpu_cached_before_groups'], 2)
        self.assertEqual(result['totals'][4]['cpu_cached_surviving_groups'], 1)
        self.assertEqual(result['requests'][0]['projections'][4]['cpu_cached_surviving_groups'], 0)
        self.assertEqual(result['requests'][1]['projections'][4]['cpu_cached_surviving_groups'], 1)

    def test_counter_payload_sequence_and_truncation_rejected(self):
        text = fixture()
        for bad in (text.replace('groups=8 hits=2', 'groups=8 hits=3'),
                    text.replace('logical_pcie_weight_bytes=32', 'logical_pcie_weight_bytes=48'),
                    text.replace('"sequence": 2', '"sequence": 3'),
                    text.rsplit('strata readonly miss cache: cumulative', 1)[0]):
            with self.subTest(bad=bad[-120:]), self.assertRaises(ValueError):
                self.analyze_text(bad)

    def test_promotion_opportunity_and_footer_accounting(self):
        result = self.analyze_text(promotion_fixture(), require_exchanges=True)
        promotion = result['promotion_opportunity']
        self.assertTrue(promotion['committed_counter_exact'])
        self.assertEqual(promotion['batches'], 2)
        self.assertEqual(promotion['totals'][4]['committed_promotions'], 3)
        self.assertEqual(promotion['totals'][4]['cached_promotions'], 2)
        self.assertEqual(promotion['totals'][4]['reusable_gpu_bytes'], 32)
        self.assertEqual(promotion['totals'][0]['cached_promotions'], 0)
        self.assertEqual(result['requests'][0]['exchange_opportunity']['since_prior_footer'][4]
                         ['cached_promotions'], 1)
        self.assertEqual(result['requests'][1]['exchange_opportunity']['since_prior_footer'][4]
                         ['committed_promotions'], 1)
        # The extra observation cannot mutate the GPU-only cache replay.
        self.assertEqual(result['totals'], self.analyze_text(fixture())['totals'])

    def test_promotion_bad_sequence_ownership_and_footer_rejected(self):
        text = promotion_fixture()
        for bad in (text.replace('"first": 2', '"first": 3'),
                    text.replace('"applied": 2', '"applied": 1'),
                    text.replace('[[6, 5]]', '[[5, 6]]'),
                    text.replace('[[6, 5]]', '[[512, 5]]'),
                    text.replace('[[5, 200], [10, 201]]', '[[5, 200], [10, 200]]'),
                    text.replace('3 exchanged with', '4 exchanged with'),
                    text.replace('0 blob reads', '1 blob reads'),
                    text.rsplit('strata serve: resident RAM:', 1)[0],
                    fixture()):
            with self.subTest(bad=bad[-140:]), self.assertRaises(ValueError):
                self.analyze_text(bad, require_exchanges=True)

    def test_promotion_rejects_midwindow_crosslayer_and_geometry_changes(self):
        opportunity = ExchangeOpportunity({4: Replay(4, 2)})
        shape = (2, 512, 16)
        with self.assertRaises(ValueError):
            opportunity.add(exchange(0, [[5, 200]], layers=2), shape, 1)
        with self.assertRaises(ValueError):
            opportunity.add(exchange(0, [[5, 600]], layers=2), shape, 2)
        with self.assertRaises(ValueError):
            opportunity.add(exchange(0, [[5, 200]], layers=1), shape, 2)
        self.assertEqual(opportunity.count, 0)


if __name__ == '__main__':
    unittest.main()
