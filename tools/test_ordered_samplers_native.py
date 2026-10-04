"""Real HTTP gate; run against the ordered-host-v1 native branch, never MockEngine."""
import argparse, json, pathlib, time, urllib.request, urllib.error, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))

PROFILES = {
    'temperature': dict(chain=['temperature'],temperature=1.5),
    'minp-hot': dict(chain=['min_p','temperature'],min_p=.05,temperature=1.5),
    'hot-minp': dict(chain=['temperature','min_p'],min_p=.05,temperature=1.5),
    'sigma-hot': dict(chain=['top_n_sigma','temperature'],top_n_sigma=2,temperature=1.5),
    'xtc-hot': dict(chain=['top_k','min_p','xtc','temperature'],top_k=16,min_p=.04,
                    xtc_probability=1,xtc_threshold=.15,temperature=.9),
    'hot-xtc': dict(chain=['top_k','min_p','temperature','xtc'],top_k=16,min_p=.04,
                    xtc_probability=1,xtc_threshold=.15,temperature=.9),
}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',default='http://127.0.0.1:18765'); p.add_argument('--output',required=True)
    p.add_argument('--oracle-only',action='store_true'); a=p.parse_args()
    out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    headers={'Content-Type':'application/json'}
    import os
    if os.getenv('STRATA_API_KEY'): headers['Authorization']='Bearer '+os.environ['STRATA_API_KEY']
    with urllib.request.urlopen(urllib.request.Request(a.base_url+'/props',headers=headers)) as r: props=json.load(r)
    assert props['strata_capabilities']['samplers']=='ordered-host-v1'
    cases=[]
    for name,profile in PROFILES.items():
        cases.append((name,dict(model='x',messages=[dict(role='user',content='Name one useful workshop tool. Answer with one word.')],
                               max_tokens=1,reasoning_effort='none',seed=675,logprobs=True,top_logprobs=5,
                               strata_sampler={**profile,'inspect':True})))
    if not a.oracle_only:
        for name,profile in PROFILES.items():
            cases.append((name+'-grammar',{**cases[0][1],'max_tokens':8,
                'grammar':'root ::= "A" | "B" | "C" | "D"', 'strata_sampler':{**profile,'inspect':True}}))
        schema={'type':'object','properties':{'answer':{'enum':['A','B']}},'required':['answer'],'additionalProperties':False}
        cases.append(('json',{**cases[1][1],'max_tokens':64,'response_format':{
            'type':'json_schema','json_schema':{'name':'choice','strict':True,'schema':schema}}}))
        cases.append(('stream',{**cases[-1][1],'stream':True}))
        plain={**cases[1][1],'max_tokens':12,'strata_sampler':{**PROFILES['minp-hot']}}
        plain.pop('logprobs');plain.pop('top_logprobs');cases.append(('without-logprobs',plain))
    result=[]
    for name,body in cases:
        start=time.perf_counter()
        req=urllib.request.Request(a.base_url+'/v1/chat/completions',json.dumps(body).encode(),headers)
        with urllib.request.urlopen(req,timeout=180) as r: raw=r.read(); status=r.status
        (out/(name+'.txt')).write_bytes(raw)
        chunks=[]
        if body.get('stream'):
            chunks=[json.loads(l[6:]) for l in raw.decode().splitlines() if l.startswith('data: {')]
            assert b'data: [DONE]' in raw and not any('error' in c for c in chunks)
            from serve.server import openai_collect
            reply=openai_collect(chunks)
        else: reply=json.loads(raw)
        choice=reply['choices'][0]; message=choice['message']; entries=(choice.get('logprobs') or {}).get('content') or []
        if body.get('strata_sampler',{}).get('inspect'):
            assert entries and all('strata_sampling' in e for e in entries),(name,reply)
            for e in entries:
                receipt=e['strata_sampling']
                assert [s['operator'] for s in receipt['stages']]==['grammar']+body['strata_sampler']['chain']
                assert 0 < receipt['probability'] <= 1
        if 'grammar' in body: assert message['content'] in ['A','B','C','D']
        if 'response_format' in body: assert json.loads(message['content']) in [{'answer':'A'},{'answer':'B'}]
        result.append(dict(case=name,request=body,response=reply,chunks=chunks,wall_ms=(time.perf_counter()-start)*1000))
        (out/'result.json').write_text(json.dumps(dict(provenance='native-strata',props=props,cases=result),indent=2),encoding='utf-8')
        print(name, 'PASS',message.get('content'),flush=True)
    (out/'result.json').write_text(json.dumps(dict(provenance='native-strata',props=props,cases=result),indent=2),encoding='utf-8')
if __name__=='__main__':main()
