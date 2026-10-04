"""Synthetic protocol/byte fixtures; native numerical evidence is a separate test."""
import io
import json
import queue
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from serve.frontend import ChatTemplate
from serve.json_output import prepare_chat_json, strict_json, json_chunks
from serve.logprobs import Probability, ScoredToken, parse_score, validate_logprobs
from serve.server import (ByteTokenizer, MockEngine, Service, StrataEngine, StructuredOutputError,
                          openai_chunks, openai_collect, serve)

ROOT = Path(__file__).resolve().parents[1]


class Bytes(ByteTokenizer):
    def token_bytes(self, token):
        return self.SPECIALS[token - 256].encode() if token >= 256 else bytes([token])


class SyntheticScores(MockEngine):
    info = {"logprobs": "raw-v1"}
    def generate(self, ids, max_new, sampling, cancel, embeddings=None):
        count = validate_logprobs(sampling)
        self.closed = False
        try:
            for i, token in enumerate(super().generate(ids, max_new, sampling, cancel, embeddings)):
                yield token if count is None else ScoredToken(i, token, -0.25,
                    tuple(Probability(token if k == 0 else (token + k) % 256, -0.25-k) for k in range(count)))
        finally:
            self.closed = True


def service(text, tokenizer=None):
    tok = tokenizer or Bytes()
    engine = SyntheticScores(tok, text)
    return Service(engine, tok, ChatTemplate(ROOT/'serve/chat_template.jinja'))


def chunks(svc, thinking=False, limit=512, **kw):
    req = dict(logprobs=True, top_logprobs=2, **kw)
    return list(openai_chunks(svc, req, [1, 2, 3], thinking, None, limit, threading.Event()))


class Validation(unittest.TestCase):
    def test_ranges_and_null(self):
        for req in ({}, {"logprobs": None}, {"logprobs":False,"top_logprobs":None}):
            self.assertIsNone(validate_logprobs(req))
        for count in (0, 1, 20, None):
            self.assertEqual(validate_logprobs(dict(logprobs=True,top_logprobs=count)), count or 0)
        for req in ({"logprobs":1}, {"logprobs":"true"}, {"top_logprobs":0},
                    {"logprobs":True,"top_logprobs":True}, {"logprobs":True,"top_logprobs":1.0},
                    {"logprobs":True,"top_logprobs":21}, {"logprobs":True,"top_logprobs":-1},
                    {"logprobs":True,"n":True}, {"logprobs":True,"n":2},
                    {"logprobs":True,"strata_mcp":True}, {"logprobs":True,"stop":["x"]}):
            with self.subTest(req=req), self.assertRaises(ValueError): validate_logprobs(req)

    def test_transport_rejects_corruption(self):
        good = 'LP 0 raw 65 -0.5 2 65:-0.5 66:-1.5'
        self.assertEqual(parse_score(good, 0, 2).id, 65)
        for bad in (good.replace('LP 0', 'LP 1'),good.replace('65 -0.5', '65 nan'),
                    good.replace('66:-1.5','65:-1.5'),good.replace('66:-1.5','66:inf'),
                    good.replace('65:-0.5','65:-0.4'),good.replace('2 65:', '1 65:'),
                    good+' 5:-6',good.replace('raw','missing'), 'LP 0 raw 65 -1 0 ignored'):
            with self.subTest(bad=bad), self.assertRaises(ValueError): parse_score(bad,0,2)


class Content(unittest.TestCase):
    def assert_content(self, text, thinking=False, expected=None):
        stream = chunks(service(text), thinking=thinking)
        result = openai_collect(stream)
        choice = result['choices'][0]
        expected = text if expected is None else expected
        self.assertEqual(choice['message']['content'], expected or None)
        entries = choice['logprobs']['content']
        self.assertEqual(bytes(b for t in entries for b in t['bytes']), expected.encode())
        self.assertTrue(all(len(t['top_logprobs']) == 2 for t in entries))
        again = openai_collect(chunks(service(text), thinking=thinking))
        for item in (result, again):
            for call in item['choices'][0]['message'].get('tool_calls', []):
                call['id'] = '<generated-call-id>'
        self.assertEqual(result['choices'], again['choices'])
        self.assertEqual(result['usage'], again['usage'])
        return choice

    def test_first_token(self):
        result = openai_collect(chunks(service('AB'),limit=1))
        choice=result['choices'][0]
        self.assertEqual(choice['message']['content'],'A')
        self.assertEqual(choice['finish_reason'],'length')
        self.assertEqual(choice['logprobs']['content'][0]['bytes'],[65])

    def test_utf8_spaces_and_buffered_newlines(self):
        self.assert_content(' A\U0001f642\n\nB\n')

    def test_hidden_reasoning(self):
        self.assert_content('private thought</think>\n\nA',thinking=True,expected='A')

    def test_tool_protocol_not_content(self):
        choice=self.assert_content('<tool_call>\n<function=read>\n<parameter=path>x</parameter>\n</function>\n</tool_call>\nA',expected='A')
        self.assertEqual(choice['message']['tool_calls'][0]['function']['name'],'read')

    def test_unfinished_tool_start_is_literal(self):
        self.assert_content('<tool_call><fun')

    def test_all_reasoning_empty_content(self):
        self.assert_content('hidden',thinking=True,expected='')

    def test_partial_utf8_is_truthful_failure(self):
        svc=service('\U0001f642')
        with self.assertRaisesRegex(ValueError,'UTF-8'): chunks(svc,limit=1)
        self.assertTrue(svc.engine.closed)

    def test_hidden_visible_token_boundary_fails(self):
        class Mixed(Bytes):
            def token_bytes(self, token):
                return b'</think>\nA' if token==320 else super().token_bytes(token)
        svc=service('',Mixed()); svc.engine.script=[320]
        with self.assertRaisesRegex(ValueError,'crosses hidden'): chunks(svc,thinking=True)
        self.assertTrue(svc.engine.closed)

    def test_feature_off_unchanged(self):
        svc=service('hello')
        result=openai_collect(openai_chunks(svc,{},[1],False,None,512,threading.Event()))
        self.assertNotIn('logprobs',result['choices'][0])
        self.assertEqual(result['choices'][0]['message']['content'],'hello')


class Transport(unittest.TestCase):
    def engine(self, lines):
        engine=StrataEngine.__new__(StrataEngine)
        engine.info={'logprobs':'raw-v1'}; engine.can_stop=True; engine.silence_s=1
        engine.proc=SimpleNamespace(stdin=io.StringIO())
        engine.lines=queue.Queue()
        for line in lines: engine.lines.put(line)
        return engine

    def test_stop_drains_scores_before_next_request(self):
        engine=self.engine(['LP 0 raw 65 -1 0','LP 1 raw 66 -2 0','DONE 2 1 0 0 length',
                            'LP 0 raw 67 -3 0','DONE 1 1 0 0 length'])
        gen=engine.generate([1],2,{'logprobs':True},threading.Event())
        self.assertEqual(next(gen).id,65); gen.close()
        self.assertIn('STOP\n',engine.proc.stdin.getvalue())
        self.assertEqual([t.id for t in engine.generate([1],1,{'logprobs':True},threading.Event())],[67])

    def test_missing_metadata_and_done_mismatch(self):
        for lines in (['T 65','DONE 1 1 0 0 length'],['LP 0 raw 65 -1 0','DONE 2 1 0 0 length']):
            engine=self.engine(lines)
            with self.assertRaises(ValueError): list(engine.generate([1],1,{'logprobs':True},threading.Event()))


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc=service('A')
        cls.svc.api_key='synthetic-test-key'
        cls.httpd=serve(cls.svc,port=0)
        cls.url=f'http://127.0.0.1:{cls.httpd.server_address[1]}/v1/chat/completions'

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def post(self, options=None, auth=True):
        body=dict(model='x',messages=[dict(role='user',content='A or B')],max_tokens=1,reasoning_effort='none',logprobs=True,top_logprobs=5)
        body.update(options or {})
        headers={'Content-Type':'application/json'}
        if auth: headers['Authorization']='Bearer synthetic-test-key'
        req=urllib.request.Request(self.url,data=json.dumps(body).encode(),headers=headers)
        try: response=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as error: response=error
        with response: return response.status,response.headers.get('Content-Type'),response.read()

    def test_json_and_sse(self):
        status,_,raw=self.post(); self.assertEqual(status,200)
        choice=json.loads(raw)['choices'][0]
        status,kind,raw=self.post({'stream':True}); self.assertEqual(status,200)
        events=[json.loads(l[6:]) for l in raw.decode().splitlines() if l.startswith('data: {')]
        self.assertEqual(choice,openai_collect(events)['choices'][0])
        self.assertIn('text/event-stream',kind)

    def test_invalid_and_old_native_preflight(self):
        for req in ({'top_logprobs':True},{'logprobs':False,'top_logprobs':5}):
            status,kind,_=self.post({**req,'stream':True})
            self.assertEqual(status,400); self.assertIn('application/json',kind)
        with patch.object(self.svc.engine,'info',{}):
            status,kind,raw=self.post({'stream':True})
            self.assertEqual(status,400); self.assertIn('application/json',kind)
            self.assertIn(b'raw-v1',raw)

    def test_auth(self):
        self.assertEqual(self.post(auth=False)[0],401)


class Json(unittest.TestCase):
    def test_exact_bytes_validation(self):
        output=prepare_chat_json({'type':'json_schema','json_schema':{'name':'answer','strict':True,
            'schema':{'type':'object','properties':{'x':{'const':1}},'required':['x'],'additionalProperties':False}}})
        text='{ "x" : 1 }'
        source=iter(chunks(service(text)))
        # Use a closeable iterator, as the production service supplies.
        def stream(): yield from source
        result=openai_collect(json_chunks(stream(),output))
        self.assertEqual(result['choices'][0]['message']['content'],text)
        with self.assertRaises(ValueError): output.validate('{"x":2}')

    def test_strict_json_and_external_refs(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":1e400}','"\\ud800"'):
            with self.assertRaises(ValueError): strict_json(raw)
        with self.assertRaisesRegex(ValueError,'local schema'):
            prepare_chat_json({'type':'json_schema','json_schema':{'name':'a','schema':{'$ref':'https://invalid.invalid/schema'}}})

    def test_missing_validator_rejected(self):
        with patch.dict('sys.modules',{'jsonschema':None}), self.assertRaisesRegex(ValueError,'no weaker'):
            prepare_chat_json({'type':'json_object'})


if __name__ == '__main__': unittest.main()
