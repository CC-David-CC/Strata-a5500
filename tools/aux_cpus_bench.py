"""Paired fleet #1598 probe. Real native engine; loopback HTTP; no Codi service.

Interleave off/on and include off/off controls. Preserve every response, engine
timing and Linux thread-affinity snapshot. Checkpoints are disabled for fresh
requests so a faster second request is not an unnoticed KV-cache hit.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, statistics, sys, threading, time, traceback
from pathlib import Path
import urllib.request

ROOT=Path('/home/dflanag3/strata-aux1598-20261008')
SOURCE=ROOT/'source'
sys.path[:0]=[str(SOURCE),str(SOURCE/'tools')]
from serve.server import Service, StrataEngine, Server, make_handler, engine_args, child_env
from serve.frontend import ChatTemplate
import strata_tokenizer as ST

PROMPTS={
 'code':'Write a complete Python implementation of an LRU cache using OrderedDict. Explain its edge cases and include unit tests. Use at least 250 words.',
 'prose':'Explain how a compiler transforms Python source into executable behavior. Cover parsing, bytecode, interpretation, and optimization in at least 250 words.'
}

def snapshot(pid):
    result={}
    for p in Path(f'/proc/{pid}/task').glob('*/status'):
        try:
            d=dict(line.split(':',1) for line in p.read_text().splitlines() if ':' in line)
            result[p.parent.name]={k:d[k].strip() for k in ('Name','Cpus_allowed_list','voluntary_ctxt_switches','nonvoluntary_ctxt_switches')}
            result[p.parent.name]['schedstat']=[int(x) for x in (p.parent/'schedstat').read_text().split()]
        except (OSError,KeyError):pass
    return result

def summarize(rows):
    groups={}
    for r in rows:
        if r['phase']=='warmup':continue
        key=(r['phase'],r['kind'],r['arm'])
        groups.setdefault(key,[]).append(r)
    summary=[]
    for (phase,kind,arm),rs in groups.items():
        good=[r for r in rs if not r.get('error')]
        summary.append(dict(phase=phase,kind=kind,arm=arm,n=len(good),errors=len(rs)-len(good),
          decode_tps=statistics.median(r['timings']['predicted_per_second'] for r in good) if good else None,
          ttft_s=statistics.median(r['ttft_s'] for r in good) if good else None,
          prompt_tps=statistics.median(r['timings']['prompt_per_second'] or 0 for r in good) if good else None,
          host_involuntary=statistics.median(r['host_involuntary'] for r in good) if good else None))
    pairs={}
    for r in rows:
        if r['phase'] not in ('decode','prefill','control','cached') or r.get('error'):continue
        pairs.setdefault((r['phase'],r['pair']),[]).append(r)
    comparisons=[]
    for (phase,pair),rs in pairs.items():
        if len(rs)!=2:continue
        a,b=sorted(rs,key=lambda r:r['arm'])
        comparisons.append(dict(phase=phase,pair=pair,kind=a['kind'],a_arm=a['arm'],b_arm=b['arm'],
             ratio_b_over_a=b['timings']['predicted_per_second']/a['timings']['predicted_per_second'],
             ttft_ratio_b_over_a=b['ttft_s']/a['ttft_s'],same_output=a['output_sha256']==b['output_sha256']))
    return dict(groups=summary,pairs=comparisons)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True)
    ap.add_argument('--gpus',default='0,2,1');ap.add_argument('--split',default='19,37')
    ap.add_argument('--workers',type=int,default=27);ap.add_argument('--aux',default='auto')
    ap.add_argument('--pairs',type=int,default=12);ap.add_argument('--prefill-pairs',type=int,default=2)
    ap.add_argument('--original',action='store_true');ap.add_argument('--startup',choices=['off','on'],default='off')
    ap.add_argument('--fixed',choices=['off','on']);ap.add_argument('--no-adapt',action='store_true')
    ap.add_argument('--decode-only',action='store_true')
    args=ap.parse_args();out=ROOT/'results'/args.label;out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(Path('/home/dflanag3/CodiServer/config.json').read_text())
    original_exe=cfg['exe']
    cfg.pop('api_key',None);gpus=[int(x) for x in args.gpus.split(',')]
    cfg['gpu']=gpus if len(gpus)>1 else gpus[0]
    if len(gpus)>1:cfg['layer_split']=args.split
    else:cfg.pop('layer_split',None)
    cfg['cwd']=str(SOURCE);cfg['exe']=str(ROOT/'build/strata')
    if args.original:cfg['exe']=original_exe
    cfg['log']=str(out/'engine.log');cfg['state']=str(out/'state');native=cfg['args']
    def option(name,value):
        if name in native:native[native.index(name)+1]=str(value)
        else:native.extend([name,str(value)])
    option('--pool-workers',args.workers)
    if '--conversation-cache-spill-dir' in native:option('--conversation-cache-spill-dir',out/'kv')
    if args.no_adapt:option('--adapt-every',0)
    if args.aux!='auto':native+=['--aux-cpus',args.aux]
    elif args.startup=='on':native+=['--aux-cpus','auto']
    (out/'config.json').write_text(json.dumps(cfg,indent=2))
    (out/'manifest.json').write_text(json.dumps(dict(options=vars(args),core='b299af0e8fc9f7ee1792c63a155707cc166ae7e4',pr='91f6238284f654b7ac85f3eb9d152fa31099eda1',ported='6273bb8e',binary_sha256=hashlib.sha256(Path(cfg['exe']).read_bytes()).hexdigest(),started=time.time()),indent=2))
    p=Path(cfg['tokenizer']);v=json.loads((p/'vocab.json').read_text());tokens=[None]*len(v)
    for token,i in v.items():tokens[i]=token
    tok=ST.Tokenizer(tokens,(p/'merges.txt').read_text().split('\n'),json.loads((p/'token_type.json').read_text()))
    engine=server=None;rows=[]
    def save():
        tmp=out/'summary.tmp';tmp.write_text(json.dumps(summarize(rows),indent=2));tmp.replace(out/'summary.json')
    try:
        engine=StrataEngine(cfg['exe'],engine_args(cfg),cwd=cfg['cwd'],log=cfg['log'],env=child_env(cfg))
        svc=Service(engine,tok,ChatTemplate(p/'chat_template.jinja'),model_name='aux-affinity-benchmark')
        svc.response_summaries=False
        server=Server(('127.0.0.1',0),make_handler(svc));threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}/v1/responses';pid=engine.proc.pid
        def measure(phase,pair,kind,arm,prompt,checkpoint=False,output=128):
            on=arm=='on' or arm=='on-control'
            if args.fixed:on=args.fixed=='on'
            req=dict(model='aux-affinity-benchmark',input=prompt,max_output_tokens=output,temperature=0,
                     reasoning={'effort':'none'},stream=True,store=False,strata_checkpoint=checkpoint)
            if not args.original:req['strata_tune']={'aux_cpus':int(on)}
            before=snapshot(pid);start=time.perf_counter();first=None;final=None;text='';error=None
            try:
                request=urllib.request.Request(url,data=json.dumps(req).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=900) as stream:
                    for raw in stream:
                        if not raw.startswith(b'data: '):continue
                        event=json.loads(raw[6:])
                        if event.get('type')=='response.output_text.delta' and event.get('delta'):
                            if first is None:first=time.perf_counter()
                            text+=event['delta']
                        if event.get('type') in ('response.completed','response.incomplete','response.failed'):final=event['response']
                if not final or final['status']=='failed' or first is None:raise RuntimeError(str(final))
            except Exception as e:error=repr(e)
            elapsed=time.perf_counter()-start;after=snapshot(pid)
            invol=lambda x:int(x.get(str(pid),{}).get('nonvoluntary_ctxt_switches',0))
            row=dict(phase=phase,pair=pair,kind=kind,arm=arm,aux_on=on,request=req,
                     ttft_s=None if first is None else first-start,total_s=elapsed,error=error,text=text,
                     output_sha256=hashlib.sha256(text.encode()).hexdigest(),usage=(final or {}).get('usage'),
                     timings=copy.deepcopy(svc.last_timings),host_involuntary=invol(after)-invol(before),
                     threads_before=before,threads_after=after)
            rows.append(row)
            with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            save();print(args.label,phase,pair,kind,arm,row['timings'],'host_invol',row['host_involuntary'],error or '',flush=True)
            if error:raise RuntimeError(error)
            if not checkpoint and row['timings']['cache_n']:raise RuntimeError('Unexpected KV reuse in fresh arm')
            return row
        # Same warm-up sequence on each independent engine; excluded from results.
        for i in range(8):
            kind=['code','prose'][i%2];measure('warmup',i,kind,'off',PROMPTS[kind])
        (out/'warmed-affinity.json').write_text(json.dumps(snapshot(pid),indent=2))
        for i in range(args.pairs):
            kind=['code','prose'][i%2]
            for arm in (['off','on'] if (i//2)%2==0 else ['on','off']):
                measure('decode',i,kind,arm,PROMPTS[kind])
            if i in (3,7,11):
                for arm in ['off','off-control']:measure('control',i,kind,arm,PROMPTS[kind])
        print('DECODE_PHASE_COMPLETE',args.label,flush=True)
        for target in ([] if args.decode_only else [1024,8192]):
            ids=tok.encode('Reference notes about Python queues, clean interfaces, deterministic tests and error recovery. '*1500,parse_special=False)
            prompt=tok.decode(ids[:target])+'\nWrite a detailed Python tutorial with runnable examples in at least 250 words.'
            for i in range(args.prefill_pairs):
                for arm in (['off','on'] if i%2==0 else ['on','off']):
                    measure('prefill',f'{target}-{i}',str(target),arm,prompt,output=32)
            if target==8192:
                measure('warmup','cached-prime','8192','off',prompt,checkpoint=True,output=32)
                for i in range(4):
                    for arm in (['off','on'] if i%2==0 else ['on','off']):
                        measure('cached',i,'8192',arm,prompt,checkpoint=True)
        (out/'complete.json').write_text(json.dumps(dict(finished=time.time(),requests=len(rows))))
    except BaseException:
        (out/'error.txt').write_text(traceback.format_exc());raise
    finally:
        if server:server.shutdown();server.server_close()
        if engine:engine.close()
        save()

if __name__=='__main__':main()
