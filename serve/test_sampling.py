"""Synthetic boundary/transport tests; native model evidence is recorded separately."""
import json
import threading
import unittest
from copy import deepcopy
from unittest.mock import patch
from serve.sampling import validate_sampler, sampler_keys, parse_sampling
from serve.test_logprobs import Transport, Http, Bytes
from serve.logprobs import score_json

PROFILE = {'chain':['min_p','temperature'], 'min_p':.05, 'temperature':1.5, 'inspect':True}
REQUEST = {'strata_sampler':PROFILE, 'logprobs':True, 'seed':675}
RECEIPT = dict(index=0,id=65,probability=.7,support=2,entropy=.61,selection_ms=1,
               stages=[dict(operator=op,support=2,entropy=.61) for op in ['grammar','min_p','temperature']],
               top=[dict(id=65,probability=.7),dict(id=66,probability=.3)])

class Validation(unittest.TestCase):
    def test_valid_and_keys(self):
        self.assertIsNone(validate_sampler({}))
        self.assertEqual(validate_sampler(REQUEST),PROFILE)
        self.assertIn('sampler_chain=min_p,temperature',sampler_keys(REQUEST))
        self.assertIn('sampler_inspect=1',sampler_keys(REQUEST))
        self.assertNotIn('sampler_seed',sampler_keys(REQUEST))
    def test_reject_not_ignore(self):
        variants = [None, {}, {**PROFILE,'chain':['dry','temperature']}, {**PROFILE,'min_p':True},
                    {**PROFILE,'temperature':float('nan')}, {**PROFILE,'dry_multiplier':.8},
                    {**PROFILE,'chain':['temperature']}, {**PROFILE,'chain':['min_p','min_p','temperature']},
                    {**PROFILE,'chain':['min_p']}, {**PROFILE,'inspect':1}]
        for profile in variants:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate_sampler({**REQUEST,'strata_sampler':profile})
        for fields in ({'temperature':1},{'top_k':64},{'logprobs':False},{'seed':0},{'seed':True},
                       {'logit_bias':{'1':4}}, {'strata_tune':{'spec_min_p':.9}}, {'stop':['x']}):
            with self.subTest(fields=fields), self.assertRaises(ValueError): validate_sampler({**REQUEST,**fields})
    def test_corrupt_receipt(self):
        self.assertEqual(parse_sampling('SP '+json.dumps(RECEIPT),0),RECEIPT)
        for fields in ({'index':1},{'probability':float('nan')},{'support':0},{'top':[]},{'id':True},{'stages':[]}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                parse_sampling('SP '+json.dumps({**RECEIPT,**fields}),0)

class OrderedTransport(Transport):
    def engine(self, lines):
        e=super().engine(lines); e.info['samplers']='ordered-host-v1'; return e
    def test_receipt_alignment_and_drain(self):
        sp='SP '+json.dumps(RECEIPT)
        e=self.engine([sp,'LP 0 raw 65 -1 0','DONE 1 1 0 0 length'])
        token=list(e.generate([1],1,REQUEST,threading.Event()))[0]
        wire=score_json(Bytes(),token)
        self.assertEqual(wire['logprob'],-1)
        self.assertEqual(wire['strata_sampling']['probability'],.7)
        self.assertEqual(wire['strata_sampling']['top'][1]['token'],'B')
        for lines in ([sp,sp,'DONE 0 1 0 0 length'],['LP 0 raw 65 -1 0','DONE 1 1 0 0 length'],
                      [sp,'LP 0 raw 66 -1 0','DONE 1 1 0 0 length'],[sp,'DONE 0 1 0 0 length']):
            e=self.engine(lines)
            with self.assertRaises(ValueError): list(e.generate([1],1,REQUEST,threading.Event()))
    def test_cancel_between_receipts(self):
        sp='SP '+json.dumps(RECEIPT)
        sp1='SP '+json.dumps({**RECEIPT,'index':1})
        e=self.engine([sp,'LP 0 raw 65 -1 0',sp1,'LP 1 raw 65 -1 0','DONE 2 1 0 0 length',
                       sp,'LP 0 raw 65 -1 0','DONE 1 1 0 0 length'])
        gen=e.generate([1],2,REQUEST,threading.Event()); next(gen); gen.close()
        self.assertIn('STOP\n',e.proc.stdin.getvalue())
        self.assertEqual(len(list(e.generate([1],1,REQUEST,threading.Event()))),1)

class OrderedHttp(Http):
    def test_sampler_errors_before_sse(self):
        for profile in (PROFILE,{**PROFILE,'chain':['dry','temperature']}):
            status,kind,raw=self.post({'strata_sampler':profile,'stream':True})
            self.assertEqual(status,400); self.assertIn('application/json',kind)
        self.assertEqual(self.post({'strata_sampler':PROFILE},auth=False)[0],401)

if __name__ == '__main__': unittest.main()
