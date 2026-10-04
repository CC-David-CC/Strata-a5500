import json
import unittest
from analyze_q8_miss_cache import PREFIX,load_groups,replay


def trace(items):
    return '\n'.join(PREFIX+json.dumps(dict(schema=1,sequence=i,layer=l,layers=2,per_layer=8,bytes=5222400,experts=es))
                     for i,(l,es) in enumerate(items))


class MissCache(unittest.TestCase):
    def test_repeat_and_zero(self):
        g=load_groups(trace([(0,[1,2]),(0,[2,1])]))
        self.assertEqual(replay(g,0)['hit_groups'],0)
        self.assertEqual(replay(g,2)['hit_groups'],2)
        self.assertEqual(replay(g,2)['avoided_upload_payload_bytes'],10444800)

    def test_protect_later_hit_in_same_group(self):
        g=load_groups(trace([(0,[1]),(0,[2,1]),(0,[1])]))
        r=replay(g,1)
        self.assertEqual(r['hit_groups'],2)
        self.assertEqual(r['bypassed_groups'],1)

    def test_layer_keys_and_capacity(self):
        g=load_groups(trace([(0,[1]),(1,[1]),(0,[1]),(1,[1])]))
        self.assertEqual(replay(g,1)['hit_groups'],0)
        self.assertEqual(replay(g,1,True)['hit_groups'],2)
        self.assertEqual(replay(g,1,True)['extra_gpu_bytes'],10444800)

    def test_reject_bad_trace(self):
        with self.assertRaises(ValueError):load_groups(trace([(0,[1]),(0,[2])]).splitlines()[1])
        with self.assertRaises(ValueError):load_groups(trace([(0,[1,1])]))
        with self.assertRaises(ValueError):load_groups(trace([(2,[1])]))


if __name__=='__main__':unittest.main()
