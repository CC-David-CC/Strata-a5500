"""Check trace accounting and bounded-cache behavior before model forecasts."""
import json
import unittest
from analyze_q8_retained_copies import PREFIX, load_batches, replay


def trace(groups, blob=5222400):
    count, lines = 0, []
    for pairs in groups:
        row = dict(schema=1, first=count, experts=8, per_layer=8, bytes=blob,
                   applied=len(pairs), pairs=pairs)
        lines.append(PREFIX + json.dumps(row))
        count += len(pairs)
    return '\n'.join(lines)


class RetainedCopies(unittest.TestCase):
    def test_ping_pong_and_payload(self):
        b = load_batches(trace([[(2, 0)], [(0, 2)], [(3, 0)], [(0, 3)]]))
        self.assertEqual(replay(b, 0)['avoided_d2h_payload_bytes'], 0)
        for policy in ('fifo', 'oracle'):
            r = replay(b, 1, policy)
            self.assertEqual(r['avoided_experts_per_batch'], [0, 1, 1, 1])
            self.assertEqual(r['avoided_d2h_payload_bytes'], 3 * 5222400)

    def test_batch_consumes_copies_before_replacement(self):
        b = load_batches(trace([[(2, 0), (3, 1)], [(0, 3), (1, 2)]]))
        self.assertEqual(replay(b, 1)['avoided_experts_per_batch'], [0, 1])
        self.assertEqual(replay(b, 2)['avoided_experts_per_batch'], [0, 2])

    def test_oracle_is_not_ordinary_fifo(self):
        b = load_batches(trace([[(2, 0)], [(3, 1)], [(0, 2)]]))
        self.assertEqual(replay(b, 1, 'fifo')['avoided_d2h_payload_bytes'], 0)
        self.assertEqual(replay(b, 1, 'oracle')['avoided_d2h_payload_bytes'], 5222400)

    def test_reject_lost_records_and_invalid_ownership(self):
        good = trace([[(2, 0)], [(0, 2)]])
        with self.assertRaises(ValueError): load_batches(good.splitlines()[1])
        with self.assertRaises(ValueError): load_batches(trace([[(2, 0)], [(2, 1)]]))
        with self.assertRaises(ValueError): load_batches(trace([[(2, 0), (3, 0)]]))
        with self.assertRaises(ValueError): load_batches(trace([[(2, 9)]]))


if __name__ == '__main__':
    unittest.main()
