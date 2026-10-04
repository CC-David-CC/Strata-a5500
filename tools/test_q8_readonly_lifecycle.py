#!/usr/bin/env python3
"""Private full-model gate for immutable secondary GPU copies; not a TPS benchmark."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'tools')]
from configure_rtxpro import configure
from bench_mtp_modes import set_option
from conversation_cache_parity import state_hashes, load_tokenizer, require
from serve.server import StrataEngine, child_env


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    opt=ap.parse_args()
    plan=json.loads(opt.plan.read_text())
    engine_root=Path(plan['engine'])
    source=(engine_root/'source-commit.txt').read_text().strip()
    sha=hashlib.sha256((engine_root/'build/strata').read_bytes()).hexdigest()
    gate=json.loads(Path(plan['component_status']).read_text())
    require(gate.get('completed') and gate.get('engine_sha256')==sha,'Component gate/binary mismatch')
    reference=json.loads(Path(plan.get('prompt_reference_status',plan['reference_status'])).read_text())
    require(reference.get('completed'),'Prompt reference incomplete')
    prompt_dir=Path(reference['matrix']).parent/'32768-mtp-duplex'
    prompts={task:json.loads((prompt_dir/(task+'.tokens.json')).read_text()) for task in ('coding','editing')}
    require(all(len(p)==32768 for p in prompts.values()),'Wrong prompt size')
    opt.output.mkdir(parents=True,exist_ok=False)
    result=dict(source=source,harness_source=(ROOT/'source-commit.txt').read_text().strip(),engine_sha256=sha,
        scope='Q8_0 FP16 native32K,40960 allocation,15472primaryslots. Plain and MTP. Matched normal/checkpoint request tokens and main-model states; STOP after16 delivered tokens. STOP work may differ with timing; any unequal-work post-cancel comparison is qualified, not claimed exact.',
        arms=[],completed=False,started=time.time())
    def save():
        tmp=opt.output/'result.tmp';tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(opt.output/'result.json')
    work_keys=('generated','drafts_accepted','drafts_offered','hits','lookups','ram_blobs','file_blobs','prompt_read')
    controls={}
    try:
        for mode,ways in [('off',0),('off',plan['ways']),('on',0),('on',plan['ways'])]:
            cfg=configure({'weights':'Q8_0','kv':'fp16','load_projection':False},engine_root,Path.home(),40960)
            for key,value in [('--expert-cache',15472),('--prompt-cache',6),('--conversation-cache-mib',4096),
                              ('--suffix-draft',0),('--spec',8),('--mtp-max-t',4),('--pcie-frac',0.55)]:
                set_option(cfg['args'],key,value)
            if mode=='off':set_option(cfg['args'],'--mtp',None)
            cfg['env'].update(STRATA_PLE_PREFAULT_THREADS='8',STRATA_EXCHANGE_ROTATE='1',
                STRATA_EXCHANGE_DUPLEX='1',STRATA_ADAPT_WORKER='0',STRATA_ADAPT_NOWAIT='0',
                STRATA_HOST_TIMING='1',STRATA_DECODE_TIMING='1',STRATA_STATE_HASH='1',
                STRATA_Q8_EXPERT_REUSE='0',STRATA_Q8_MISS_CACHE_WAYS=str(ways))
            label=mode+'-ways'+str(ways);log=opt.output/(label+'.log')
            arm=dict(label=label,mode=mode,ways=ways,config=cfg,requests=[])
            result['arms'].append(arm);save()
            engine=None
            try:
                tokenizer=load_tokenizer(Path(cfg['tokenizer']))
                suffix=tokenizer.encode('<|im_end|>\n<|im_start|>user\nContinue the implementation.<|im_end|>\n'
                    '<|im_start|>assistant\n<think>\n\n</think>\n\n',parse_special=True)
                engine=StrataEngine(cfg['exe'],cfg['args'],cfg['cwd'],str(log),child_env(cfg))
                require(engine.can_stop,'Engine does not advertise STOP')
                arm['engine_info']=dict(engine.info)
                require(engine.info['expert_slots']==15472 and engine.info['kv']=='fp16','Placement/KV changed')
                def run(name,prompt,count,cancel_at=None,require_length=True):
                    cancel=threading.Event();tokens=[];start=time.monotonic()
                    for token in engine.generate(prompt,count,{'temperature':0},cancel):
                        if token is not None:
                            tokens.append(token)
                            if cancel_at and len(tokens)>=cancel_at:cancel.set()
                    req=dict(name=name,token_ids=tokens,timings=dict(engine.last),wall_seconds=time.monotonic()-start)
                    arm['requests'].append(req);save()
                    require(engine.alive(),name+': engine exited')
                    require(engine.last.get('file_blobs',0)==0,name+': file expert reads')
                    if cancel_at:
                        require(len(tokens)==cancel_at and engine.last['finish']=='cancel',name+': STOP failed')
                    elif require_length:
                        require(len(tokens)==count and engine.last['finish']=='length',name+': output budget not reached')
                    else:
                        require(bool(tokens) and engine.last['finish'] in ('stop','length'),name+': no normal output')
                    return tokens
                run('normal',prompts['coding'],256)
                head=run('checkpoint-A',prompts['coding'],1)
                run('checkpoint-B',prompts['editing'],1)
                continuation=prompts['coding']+head+suffix
                run('checkpoint-A+',continuation,128,require_length=False)
                require(engine.last['reused']>=len(prompts['coding']),'Conversation A was not restored after B')
                run('checkpoint-B-again',prompts['editing'],1)
                run('checkpoint-A+-again',continuation,128,require_length=False)
                require(engine.last['reused']>0,'Parked checkpoint was not restored')
                run('cancel',prompts['coding'],1024,cancel_at=16)
                run('after-cancel',prompts['editing'],128)
                text=log.read_text(errors='replace');hashes=state_hashes(text)
                require(len(hashes)==len(arm['requests']),'Missing request state fingerprints')
                for req,state in zip(arm['requests'],hashes):req['state']=state
                if ways==0:
                    controls[mode]=arm
                else:
                    require('strata readonly miss cache: enabled,' in text,'Cache did not activate')
                    reports=re.findall(r'cumulative groups=(\d+) hits=(\d+) uploads=(\d+) bypasses=(\d+)',text)
                    require(reports and int(reports[-1][1])>0,'No cached GPU weights consumed')
                    arm['cache_reports']=[dict(zip(('groups','hits','uploads','bypasses'),map(int,r))) for r in reports]
                    baseline=controls[mode]['requests'];current=arm['requests']
                    comparisons=[]
                    cancel_work={k:[baseline[-2]['timings'].get(k),current[-2]['timings'].get(k)] for k in work_keys
                        if baseline[-2]['timings'].get(k)!=current[-2]['timings'].get(k)}
                    for old,new in zip(baseline,current):
                        a,b=old['token_ids'],new['token_ids']
                        first=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),None if len(a)==len(b) else min(len(a),len(b)))
                        states={k:[old['state'].get(k),new['state'].get(k)] for k in old['state'] if old['state'].get(k)!=new['state'].get(k)}
                        work={k:[old['timings'].get(k),new['timings'].get(k)] for k in work_keys if old['timings'].get(k)!=new['timings'].get(k)}
                        comparable=new['name'] not in ('cancel','after-cancel') or not cancel_work
                        comparisons.append(dict(name=new['name'],first_token_difference=first,state_differences=states,
                            work_differences=work,exact_comparison_required=comparable))
                    arm['comparisons']=comparisons;arm['cancel_work_differences']=cancel_work;save()
                    for c in comparisons:
                        if c['exact_comparison_required']:
                            require(c['first_token_difference'] is None and not c['state_differences'],c['name']+': output/state differs')
                        if c['name']=='normal':require(not c['work_differences'],'Normal request work differs')
                arm['passed']=True;print('LIFECYCLE_PASS '+label,flush=True)
            finally:
                if engine:
                    process=engine.proc;engine.close();arm['exit_code']=process.returncode if process else None
                    if arm.get('passed'):require(arm['exit_code']==0,'Engine did not exit cleanly')
                save()
        result['completed']=True
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        result['finished']=time.time();save()


if __name__=='__main__':main()
