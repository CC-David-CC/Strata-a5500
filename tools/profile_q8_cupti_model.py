#!/usr/bin/env python3
"""Measure real Q8 DRAM traffic per committed token after the queued experiments.

This uses the frozen buffer-ownership binary and validated direct CUPTI library.
There is no application/kernel replay or graph replacement. A short capture
must first match the existing 8K control. Then collect all four native 64K
paths, each with its own unprofiled reference. Profiled speed is not throughput.
"""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time

H=Path.home();R=Path(__file__).resolve().parents[1]
ENGINE=H/'src/strata-q8-exchange-rotation-1a50d913'
ENGINE_SOURCE='1a50d913bf910a1f63fbc1a0788a7083e3ca5f8c'
ENGINE_SHA='d14ed6b69a1814ce4b5c08932a47d6921a55fa0aa8dea50427ccf0782d1ad997'
PY=H/'src/Strata/.venv/bin/python'
LIBRARY=H/'src/q8-cupti-fixture-06d5f4fc/build-fleet/libcupti_decode_range.so'
LIBRARY_SHA='47d059ca1cc9040caf2247ff5fd6620eb460c0fe5125cf3397f5b19e41012450'
D=H/'fleet-downloads/rtxpro-q8-cupti-model-20261003'
PRIOR=H/'fleet-downloads/rtxpro-q8-cupti-fixture-20261003/status.json'
CONTROL_8K=H/'fleet-downloads/rtxpro-q8-capture-probe-20261003-r2/capture-probe-attempt-01/matrix.json'
MODES={'probe-mtp':('on',0,'coding',8192,128,8,2),
       'serial':('off',0,'coding',65536,512,32,16),'mtp':('on',0,'coding',65536,512,32,16),
       'ngram':('off',3,'editing',65536,512,32,16),'mtp-ngram':('on',3,'editing',65536,512,32,16)}
METRICS=('dram__bytes_op_read.sum','dram__bytes_op_write.sum','lts__t_bytes.sum')

def save(p,j):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(j,indent=2)+'\n');tmp.replace(p)

def option(args,key,value):
    if key in args:args[args.index(key)+1]=str(value)
    else:args.extend([key,str(value)])

def replay(spec_file):
    spec=json.loads(spec_file.read_text());out=Path(spec['output'])/('replay-'+str(os.getpid()))
    cmd=[PY,ENGINE/'tools/bench_mtp_modes.py','--config',spec['config'],'--output',out,
        '--input-tokens',str(spec['input_tokens']),'--output-tokens',str(spec['output_tokens']),'--mode',spec['mtp'],
        '--suffix-draft',str(spec['suffix']),'--verify-window','8','--mtp-window','4',
        '--workload','long','--repetitions','1','--cases',spec['task'],
        '--source-commit',ENGINE_SOURCE]
    subprocess.run(list(map(str,cmd)),check=True)

def worker(out):
    sys.path.insert(0,str(ENGINE/'tools'))
    from configure_rtxpro import configure
    out.mkdir(parents=True,exist_ok=False)
    assert hashlib.sha256((ENGINE/'build/strata').read_bytes()).hexdigest()==ENGINE_SHA
    if hashlib.sha256(LIBRARY.read_bytes()).hexdigest()!=LIBRARY_SHA:raise RuntimeError('Counter library changed')
    prerequisite=json.loads(PRIOR.read_text())
    fixture=json.loads(Path(prerequisite['matrix']).read_text())
    if not fixture.get('completed') or fixture['library_sha256']!=LIBRARY_SHA or len(fixture['records'])!=6:
        raise RuntimeError('Direct CUPTI fixture was not validated')
    old_control=json.loads(CONTROL_8K.read_text())
    if old_control['baseline_sha256']!=ENGINE_SHA:raise RuntimeError('8K reference binary differs')
    probe_reference=old_control['records'][0]
    if probe_reference['label']!='frozen-control' or probe_reference['exit']!=0:
        raise RuntimeError('Existing 8K control did not complete')
    state={'started':time.time(),'weights':'Q8_0','kv':'fp16','input_tokens':65536,'output_budget':512,
        'allocated_context':73728,'engine_sha256':ENGINE_SHA,'engine_source':ENGINE_SOURCE,'records':[],
        'rotation':True,'library_sha256':LIBRARY_SHA,'fixture':prerequisite['matrix'],
        'scope':'Original frozen binary; direct CUPTI user range, one pass, no replay or graph replacement. Short 8K probe then native 64K, 16-window traffic per actually committed token. Profiled timings excluded.',
        'caveat':'N-gram modes use editing, serial/MTP use coding. Cross-task ceilings are not directly comparable. GPU-only conditional ceilings omit CPU and PCIe limits.'}
    target=out/'matrix.json';save(target,state)
    try:
        for mode,(mtp,suffix,task,input_tokens,output_tokens,skip,count) in MODES.items():
            state['current']=mode;save(target,state)
            cfg=configure({'weights':'Q8_0','kv':'fp16','load_projection':False},ENGINE,H,73728)
            cfg['env'].update(STRATA_PLE_PREFAULT_THREADS='8',STRATA_ADAPT_NOWAIT='0',
                              STRATA_EXCHANGE_ROTATE='1',STRATA_FLEET_PROFILE='0')
            option(cfg['args'],'--expert-cache',16192 if mtp=='on' else 16400)
            option(cfg['args'],'--pcie-frac',-1)
            rec={'mode':mode,'task':task,'input_tokens':input_tokens,'output_budget':output_tokens,
                 'capture_skip':skip,'capture_count':count,'started':time.time()};state['records'].append(rec);save(target,state)
            completed={}
            for profiling in (False,True):
                label=mode+('-profile' if profiling else '-reference')
                if mode=='probe-mtp' and not profiling:
                    completed[False]=probe_reference['replays']
                    rec[label+'_replays']=probe_reference['replays']
                    rec['reused_control']=str(CONTROL_8K)
                    save(target,state)
                    continue
                base=out/label;base.mkdir()
                config=base/'config.json'
                if profiling:cfg['env'].update(STRATA_FLEET_PROFILE='1',STRATA_FLEET_PROFILE_SKIP=str(skip),
                    STRATA_FLEET_PROFILE_COUNT=str(count),LD_PRELOAD=str(LIBRARY),STRATA_CUPTI_OUTPUT=str(base/'traffic.json'))
                save(config,cfg)
                spec=base/'spec.json';save(spec,{'output':str(base),'config':str(config),'mtp':mtp,'suffix':suffix,'task':task,
                                              'input_tokens':input_tokens,'output_tokens':output_tokens})
                cmd=[str(PY),str(Path(__file__)),'--replay',str(spec)]
                save(base/'command.json',cmd)
                with (base/'stdout.log').open('w') as stdout,(base/'stderr.log').open('w') as stderr:
                    p=subprocess.run(cmd,stdout=stdout,stderr=stderr,timeout=2400)
                rec[label+'_exit']=p.returncode;save(target,state)
                if p.returncode:
                    rec['error']=label+' exited '+str(p.returncode)
                    raise RuntimeError(rec['error']+'; remaining modes not attempted')
                files=re.findall(r'^BENCHMARK_COMPLETED (.+)$',(base/'stdout.log').read_text(),re.M)
                replays=[]
                for filename in dict.fromkeys(files):
                    result_path=Path(filename.strip());data=json.loads(result_path.read_text())
                    case=data['runs'][0]['cases'][0]
                    log=(result_path.parent/f'engine-mtp-{mtp}.log').read_text()
                    start=re.findall(r'fleet profile start window=(\d+) committed=(\d+)',log)
                    stop=re.findall(r'fleet profile stop window=(\d+) committed=(\d+)',log)
                    if 'exchange buffer rotation enabled' not in log:
                        raise RuntimeError('Ownership rotation did not activate; placement is not the intended configuration')
                    row={'result':str(result_path),'prompt_sha256':data['prompt_sha256'],'case':case,
                         'zero_file_expert_reads':case['timings'].get('file_blobs')==0}
                    if not row['zero_file_expert_reads']:
                        raise RuntimeError('Unexpected file expert reads; RAM placement does not match the intended all-resident complement')
                    if profiling:
                        if len(start)!=1 or len(stop)!=1:raise RuntimeError('Missing unique profile boundaries')
                        a,b=tuple(map(int,start[0])),tuple(map(int,stop[0]));row.update(start=a,stop=b,committed_in_range=b[1]-a[1])
                        if a[0]!=skip or b[0]-a[0]!=count or row['committed_in_range']<=0:raise RuntimeError('Invalid capture accounting')
                    replays.append(row)
                if not replays:raise RuntimeError('No completed replay outputs')
                completed[profiling]=replays;rec[label+'_replays']=replays;save(target,state)
                if profiling:
                    counter=json.loads((base/'traffic.json').read_text())
                    if not counter.get('completed') or counter['passes']!=1 or counter['ranges']!=1 or counter['dropped'] or counter['replay'] or counter['unit']!='byte':
                        raise RuntimeError('Counter capture is incomplete')
                    if len(replays)!=1:raise RuntimeError('Unexpected multiple model executions')
                    totals=counter['metrics'];rec['counter_capture']=counter
                    same=all(x['case']['token_ids']==replays[0]['case']['token_ids'] and
                             x['start']==replays[0]['start'] and x['stop']==replays[0]['stop'] for x in replays)
                    rec['replays_agree']=same;rec['range_bytes']=totals
                    if not same:
                        rec['error']='Application replays differ; no per-token roofline accepted'
                    else:
                        n=replays[0]['committed_in_range']
                        rec['bytes_per_committed_token']={k:v/n for k,v in totals.items()}
                        dram=(totals[METRICS[0]]+totals[METRICS[1]])/n
                        if dram<=0:raise RuntimeError('No model DRAM traffic measured')
                        rec['conditional_tps_at_measured_streaming_1647_GBs']=1647e9/dram
                        rec['conditional_tps_at_advertised_1792_GBs']=1792e9/dram
                        ref=completed[False][0]['case'];prof=replays[0]['case']
                        if completed[False][0]['prompt_sha256']!=replays[0]['prompt_sha256']:
                            raise RuntimeError('Reference and profile prompts differ')
                        rec['profile_matches_reference_tokens']=ref['token_ids']==prof['token_ids']
                        work_keys=('generated','drafts_accepted','drafts_offered','hits','lookups','ram_blobs','file_blobs','file_mb','prompt_read')
                        rec['work_counter_differences']={k:[ref['timings'].get(k),prof['timings'].get(k)]
                            for k in work_keys if ref['timings'].get(k)!=prof['timings'].get(k)}
                        rec['profile_matches_reference_work']=not rec['work_counter_differences']
                        rec['first_token_difference']=next((i for i,(a,b) in enumerate(zip(ref['token_ids'],prof['token_ids'])) if a!=b),
                            None if len(ref['token_ids'])==len(prof['token_ids']) else min(len(ref['token_ids']),len(prof['token_ids'])))
                        rec['unprofiled_decode_tps']=ref['decode_tps']
                        if rec['profile_matches_reference_tokens'] and rec['profile_matches_reference_work'] and mode!='probe-mtp':
                            rec['window_traffic_full_request_throughput_proxy']=ref['decode_tps']*dram/1647e9
                            rec['proxy_limit']='16-window traffic multiplied by full-request throughput; not directly measured GPU utilization'
                        else:rec['comparison_limit']='Probe or profiled output/work differs; no matched throughput/traffic fraction'
                        if mode=='probe-mtp' and (not rec['profile_matches_reference_tokens'] or not rec['profile_matches_reference_work']):
                            raise RuntimeError('8K direct counter probe differs from reference; no 64K tests launched')
                save(target,state)
            rec['finished']=time.time();save(target,state)
        state['completed']=all('bytes_per_committed_token' in x and not x.get('error') for x in state['records'])
        if not state['completed']:raise RuntimeError('One or more DRAM measurements incomplete; inspect per-mode records')
    except BaseException as error:state['error']=repr(error);raise
    finally:state['finished']=time.time();save(target,state)

def main():
    if len(sys.argv)>1:
        if sys.argv[1]=='--worker':worker(Path(sys.argv[2]));return
        if sys.argv[1]=='--replay':replay(Path(sys.argv[2]));return
    sys.path.insert(0,str(H/'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    source=(R/'source-commit.txt').read_text().strip();base.wh.CUTOFF=time.time()+24*3600
    r=base.CgroupRun(D,source)
    r.s.update(shutdown_afterwards=False,current='waiting for direct CUPTI fixtures',dependency=str(PRIOR),
        operational_guard_not_user_deadline=True,cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF,datetime.timezone.utc).isoformat());r.save()
    lock=(H/'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while not PRIOR.exists() or not json.loads(PRIOR.read_text()).get('finished'):r.check_time();time.sleep(5)
        if not json.loads(PRIOR.read_text()).get('completed'):
            raise RuntimeError('Direct CUPTI fixture prerequisite failed; no Q8 profiling attempted')
        while True:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:r.check_time();time.sleep(5)
        step=r.gpu('q8-dram',[PY,Path(__file__),'--worker',D/'{attempt}'],{},timeout=14400)
        r.s['matrix']=str(D/step['label']/'matrix.json');r.save()
    except BaseException as error:r.finish(error);raise
    else:r.finish()

if __name__=='__main__':main()
