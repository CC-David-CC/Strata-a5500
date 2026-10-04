"""Native ordered sampler cancellation plus ordinary request after it (HTTP)."""
import argparse, json, pathlib, time
import httpx

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:18765');p.add_argument('--output',required=True)
    a=p.parse_args();root=pathlib.Path(a.output);root.mkdir(parents=True,exist_ok=True)
    import os
    headers={'Authorization':'Bearer '+os.environ['STRATA_API_KEY']} if os.getenv('STRATA_API_KEY') else {}
    body=dict(model='x',messages=[dict(role='user',content='Write a long explanation of a mechanical clock.')],
        max_tokens=300,reasoning_effort='none',logprobs=True,top_logprobs=5,seed=675,stream=True,
        strata_sampler=dict(chain=['min_p','temperature'],min_p=.05,temperature=1.5,inspect=True))
    start=time.perf_counter();chunks=[]
    with httpx.Client(base_url=a.base_url,headers=headers,timeout=180,trust_env=False) as client:
        with client.stream('POST','/v1/chat/completions',json=body) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith('data: {'):
                    chunk=json.loads(line[6:]);assert 'error' not in chunk;chunks.append(chunk)
                    if any(c.get('logprobs',{}).get('content') for c in chunk.get('choices',[]) if c.get('logprobs')): break
        stopped_at=time.perf_counter()-start
        plain={k:v for k,v in body.items() if k not in ('strata_sampler','stream')}
        plain.update(messages=[dict(role='user',content='Say exactly OK.')],max_tokens=16,temperature=0)
        r=client.post('/v1/chat/completions',json=plain);r.raise_for_status();reply=r.json()
        assert reply['choices'][0]['message']['content'].strip()=='OK',reply
        assert not any('strata_sampling' in t for t in reply['choices'][0]['logprobs']['content'])
        invalid=client.post('/v1/chat/completions',json={**body,'strata_sampler':{**body['strata_sampler'],'chain':['dry','temperature']}})
        assert invalid.status_code==400 and 'application/json' in invalid.headers['content-type']
    result=dict(provenance='native-strata',cancelled_request=body,chunks_before_disconnect=chunks,
        seconds_to_disconnect=stopped_at,next_request=plain,next_response=reply,total_seconds=time.perf_counter()-start,
        invalid_profile_status=invalid.status_code)
    (root/'lifecycle.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('PASS disconnect/drain, next ordinary request, pre-header rejection')
if __name__=='__main__':main()
