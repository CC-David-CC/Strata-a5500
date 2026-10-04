#!/usr/bin/env python3
import unittest

from analyze_q8_cached_cpu_capacity import opportunity


class CapacityTest(unittest.TestCase):
    def test_baseline_gpu_assignments_keep_slots(self):
        # Early CPU hits must not take the slot of a later baseline GPU miss.
        r=opportunity([(1,-1,2),(2,-1,1),(8,1,1),(9,1,1)],{1,2},cap=3)
        self.assertEqual(r['eligible_groups'],1)
        self.assertEqual(r['eligible_entries'],2)
        self.assertEqual(r['blocked_groups'],1)
        self.assertEqual(r['blocked_entries'],1)

    def test_full_and_empty_cache(self):
        groups=[(1,-1,1),(2,1,1),(3,0,1)]
        self.assertEqual(opportunity(groups,{1},cap=1)['eligible_groups'],0)
        self.assertEqual(opportunity(groups,set(),cap=2)['cached_cpu_groups'],0)

    def test_primary_hits_do_not_consume_staging_slots(self):
        r=opportunity([(1,0,3),(2,-1,2),(3,-1,1)],{2,3},cap=2)
        self.assertEqual((r['eligible_groups'],r['eligible_entries']),(2,3))
        self.assertEqual(r['blocked_groups'],0)

    def test_bad_capacity_rejected(self):
        with self.assertRaises(ValueError):opportunity([],set(),cap=0)
        with self.assertRaises(ValueError):opportunity([(1,1,1),(2,1,1)],set(),cap=1)


if __name__=='__main__':unittest.main()
