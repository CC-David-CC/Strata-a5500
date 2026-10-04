"""The startup guard rejects changed residency before any request is possible."""
from pathlib import Path
import tempfile
import unittest
from benchmark_startup import StartupMismatch, start_checked_engine


class Engine:
    def __init__(self, info):
        self.info = info
        self.closed = False

    def close(self):
        self.closed = True


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / 'engine.log'
        self.log.write_text('strata: PLE startup threads=8 locked=1\n')
        self.expected = dict(arena_mib=45342, expert_slots_primary=15472, kv='fp16')
        self.patterns = [r'^strata: PLE startup .*\blocked=1\b']

    def check(self, info, patterns=None):
        engine, run = Engine(info), {}
        with self.assertRaises(StartupMismatch):
            start_checked_engine(lambda: engine, self.expected, self.log,
                                 self.patterns if patterns is None else patterns, run)
            self.fail('a rejected engine must not reach the request loop')
        self.assertTrue(engine.closed)
        self.assertFalse(run['startup_precondition']['passed'])
        self.assertTrue(run['startup_precondition']['closed_after_rejection'])
        self.assertEqual(run['engine_info'], info)
        return run

    def test_accept_and_leave_engine_open_for_requests(self):
        engine, run = Engine({**self.expected, 'unrelated': 123}), {}
        self.assertIs(start_checked_engine(lambda: engine, self.expected, self.log,
                                          self.patterns, run), engine)
        self.assertFalse(engine.closed)
        self.assertTrue(run['startup_precondition']['passed'])

    def test_observed_partial_residency_rejected(self):
        run = self.check({**self.expected, 'arena_mib': 44689})
        self.assertEqual(set(run['startup_precondition']['differences']), {'arena_mib'})

    def test_missing_wrong_type_and_each_changed_placement(self):
        for key in self.expected:
            for replacement in (None, False, 'unexpected'):
                with self.subTest(key=key, replacement=replacement):
                    info = dict(self.expected)
                    if replacement is None:
                        del info[key]
                    else:
                        info[key] = replacement
                    self.check(info)

    def test_unlocked_table_rejected(self):
        self.log.write_text('strata: PLE startup threads=8 locked=0\n')
        self.check(self.expected)

    def test_disabled_guard_preserves_behavior(self):
        engine, run = Engine({}), {}
        self.assertIs(start_checked_engine(lambda: engine, None, self.log, [], run), engine)
        self.assertEqual(run, {})

    def test_invalid_expectation_fails_before_start(self):
        def forbidden():
            self.fail('invalid expectations must not load the model')
        with self.assertRaises(ValueError):
            start_checked_engine(forbidden, {}, self.log, [], {})


if __name__ == '__main__':
    unittest.main()
