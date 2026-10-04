"""Real HTTP qualification. Run with this checkout's Python dependencies.

  python tools/qualify_logprobs.py --config local.json --output evidence/target
  python tools/qualify_logprobs.py --base-url http://127.0.0.1:8080 --output evidence/client

--config owns a temporary loopback server and shuts it down. --base-url only
tests an already running server. STRATA_API_KEY supplies its optional API key.
"""
import argparse
import concurrent.futures
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from serve.server import openai_collect


@contextlib.contextmanager
def server(config, output, base_url):
    if base_url:
        yield base_url.rstrip('/'); return
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    command=[sys.executable,'-m','serve.server','--engine','strata','--config',str(Path(config).resolve()),
             '--host','127.0.0.1','--port',str(port)]
    with (output/'server.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                 start_new_session=os.name!='nt')
        try:
            url=f'http://127.0.0.1:{port}'
            for _ in range(600):
                if process.poll() is not None: raise RuntimeError('server exited; inspect server.log')
                try: urllib.request.urlopen(url+'/health',timeout=2).close(); break
                except OSError: time.sleep(1)
            else: raise TimeoutError('server startup')
            yield url
        finally:
            if process.poll() is None:
                if os.name=='nt': process.terminate()
                else: os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    if os.name=='nt': process.kill()
                    else: os.killpg(process.pid,signal.SIGKILL)
                    process.wait()


def check_scores(response):
    choice=response['choices'][0]
    entries=choice['logprobs']['content']
    content=choice['message'].get('content') or ''
    assert bytes(b for t in entries for b in t['bytes']) == content.encode('utf-8')
    for entry in entries:
        assert math.isfinite(entry['logprob']) and entry['logprob'] <= 0
        top=entry['top_logprobs']
        assert all(math.isfinite(t['logprob']) and t['logprob'] <= 0 for t in top)
        assert all(a['logprob']>=b['logprob'] for a,b in zip(top,top[1:]))
        assert sum(math.exp(t['logprob']) for t in top) <= 1 + 1e-9
    return choice


def run(url, output, temperature=0):
    records=[]
    base=dict(model='x',messages=[dict(role='user',content='Answer with only A or B: is the sky blue? A) yes B) no')],
              max_tokens=1,temperature=temperature,seed=675,top_p=0.95,top_k=20,
              logprobs=True,top_logprobs=5,reasoning_effort='none')
    def request(name, changes=None, expected=200):
        body={**base,**(changes or {})}
        (output/(name+'-request.json')).write_text(json.dumps(body,indent=2,ensure_ascii=False),encoding='utf-8')
        headers={'Content-Type':'application/json'}
        if os.environ.get('STRATA_API_KEY'): headers['Authorization']='Bearer '+os.environ['STRATA_API_KEY']
        req=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(body).encode(),headers=headers)
        begin=time.monotonic()
        try: response=urllib.request.urlopen(req,timeout=600)
        except urllib.error.HTTPError as exc: response=exc
        with response: status=response.status; raw=response.read()
        elapsed=time.monotonic()-begin
        (output/(name+'-response.txt')).write_bytes(raw)
        record=dict(name=name,status=status,wall_seconds=elapsed)
        records.append(record)
        (output/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        assert status==expected,(name,status,raw[:1000])
        if status!=200: return json.loads(raw)
        if body.get('stream'):
            events=[json.loads(line[6:]) for line in raw.decode().splitlines() if line.startswith('data: {')]
            assert not any('error' in e for e in events),(name,events[-2:])
            data=openai_collect(events)
        else: data=json.loads(raw)
        if body['logprobs']: check_scores(data)
        else: assert 'logprobs' not in data['choices'][0]
        record['timings']=data.get('timings'); record['usage']=data['usage']
        record['finish']=data['choices'][0]['finish_reason']
        (output/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        print(name,status,data['choices'][0]['message'],flush=True)
        return data

    first=request('first-cold')
    warm=request('first-warm')
    stream=request('first-stream',{'stream':True})
    assert warm['choices']==stream['choices']
    request('disabled',{'logprobs':False,'top_logprobs':None})
    request('top-zero',{'top_logprobs':0})
    request('top-twenty',{'top_logprobs':20})
    request('invalid-stream',{'stream':True,'top_logprobs':True},400)
    prompt=[dict(role='user',content='Write the numbers from 1 to 30, separated by commas. Do not add commentary.')]
    long=request('long',{'messages':prompt,'max_tokens':40})
    long_stream=request('long-stream',{'messages':prompt,'max_tokens':40,'stream':True})
    assert long['choices']==long_stream['choices']
    disabled=request('long-disabled',{'messages':prompt,'max_tokens':40,'logprobs':False,'top_logprobs':None})
    assert disabled['choices'][0]['message']==long['choices'][0]['message']
    forced=request('grammar-outside-top',{'grammar':'root ::= "Z"','max_tokens':8})
    assert forced['choices'][0]['message']['content']=='Z'
    entry=forced['choices'][0]['logprobs']['content'][0]
    assert 'Z' not in [t['token'] for t in entry['top_logprobs']]
    unicode=request('grammar-unicode',{'grammar':'root ::= " é🙂"','max_tokens':16,'stream':True})
    assert unicode['choices'][0]['message']['content']==' é🙂'
    schema={'type':'object','properties':{'decision':{'enum':['A','B']}},'required':['decision'],'additionalProperties':False}
    fmt={'type':'json_schema','json_schema':{'name':'decision','strict':True,'schema':schema}}
    structured=request('json-schema',{'response_format':fmt,'max_tokens':64})
    assert json.loads(structured['choices'][0]['message']['content'])['decision'] in ('A','B')
    request('json-schema-stream',{'response_format':fmt,'max_tokens':64,'stream':True})
    request('json-object',{'response_format':{'type':'json_object'},'max_tokens':64})
    request('json-thinking',{'response_format':fmt,'reasoning_effort':'low','reasoning_budget_tokens':16,'max_tokens':128})
    # Independent requests compete for the existing service FIFO.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(request,'queued-'+str(i)) for i in range(2)]
        for f in futures: assert f.result()['choices']==warm['choices']
    # CPU reduction overhead: alternate warmed, identical greedy requests.
    for i in range(6):
        request('cost-'+str(i),{'messages':prompt,'max_tokens':40,'logprobs':i%2==1,'top_logprobs':5 if i%2 else None})
    return records


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--config');group.add_argument('--base-url')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--temperature',type=float,default=0)
    ap.add_argument('--examples-only',action='store_true')
    args=ap.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    with server(args.config,args.output,args.base_url) as url:
        records=run_examples(url,args.output) if args.examples_only else run(url,args.output,args.temperature)
    (args.output/'PASS.txt').write_text(f'{len(records)} real HTTP requests passed.\n',encoding='utf-8')


def run_examples(url,output):
    records=[]
    paths=sorted((ROOT/'examples/logprobs').glob('*.json'))
    requests=[(p.stem,json.loads(p.read_text(encoding='utf-8'))) for p in paths]
    repeated='alpha beta gamma delta epsilon zeta eta theta\n'*20
    for constraint in (False,True):
        body=dict(model='x',messages=[dict(role='user',content='Repeat exactly the following text, without quotes or fences:\n\n'+repeated)],
                  max_tokens=160,temperature=0,reasoning_effort='none',logprobs=True,top_logprobs=5)
        if constraint: body['grammar']='root ::= '+json.dumps(repeated)
        requests.append(('suffix-repetition'+('-grammar' if constraint else ''),body))
    for name,body in requests:
        (output/(name+'-request.json')).write_text(json.dumps(body,indent=2,ensure_ascii=False),encoding='utf-8')
        request=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=600) as response: raw=response.read(); status=response.status
        (output/(name+'-response.txt')).write_bytes(raw)
        if body.get('stream'):
            events=[json.loads(l[6:]) for l in raw.decode().splitlines() if l.startswith('data: {')]
            assert not any('error' in e for e in events),events[-2:]
            result=openai_collect(events)
        else: result=json.loads(raw)
        choice=check_scores(result)
        if name=='tool-call': assert choice['message'].get('tool_calls'),choice
        records.append(dict(name=name,status=status,timings=result.get('timings'),content_tokens=len(choice['logprobs']['content'])))
        (output/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        print(name,status,repr(choice['message'])[:200],flush=True)
    return records


if __name__=='__main__': main()
