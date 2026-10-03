#!/usr/bin/env python3
"""Counter/denominator guards for the verification-width experiment."""
import unittest
from bench_verify_widths import parse_histogram, validate_observation


class WidthObservationTest(unittest.TestCase):
    def check(self, **changes):
        values = dict(job={'path': 'oracle', 'width': 3}, tokens=[10, 11, 12, 13],
                      expected=[10, 11, 12, 13], timings={'reused': 0, 'drafts_accepted': 2, 'drafts_offered': 2},
                      widths={1: 1, 2: 0, 3: 1}, committed={1: 1, 2: 0, 3: 1})
        values.update(changes)
        validate_observation(**values)

    def test_exact_committed_denominator(self):
        self.check()
        with self.assertRaisesRegex(ValueError, 'every emitted'):
            self.check(committed={1: 1, 3: 2})

    def test_oracle_cannot_claim_rejected_positions(self):
        with self.assertRaisesRegex(ValueError, 'rejected'):
            self.check(timings={'drafts_accepted': 1, 'drafts_offered': 2})

    def test_width_cap_and_fresh_prompt(self):
        with self.assertRaisesRegex(ValueError, 'width cap'):
            self.check(job={'path': 'oracle', 'width': 2})
        with self.assertRaisesRegex(ValueError, 'cached state'):
            self.check(timings={'reused': 10})

    def test_changed_or_shorter_answer_is_not_a_win(self):
        for answer in ([10, 15, 12, 13], [10, 11, 12]):
            with self.assertRaisesRegex(ValueError, 'Token/reference'):
                self.check(tokens=answer)

    def test_unique_histogram(self):
        line = 'strata serve: WINDOW_HIST widths=1:1,2:0,3:1 committed=1:1,2:0,3:1'
        self.assertEqual(parse_histogram(line), [{1: 1, 2: 0, 3: 1}] * 2)
        with self.assertRaisesRegex(ValueError, 'Expected one'):
            parse_histogram(line + '\n' + line)


if __name__ == '__main__':
    unittest.main()
