#!/usr/bin/env python3
"""Bounded PCIe exchange microbenchmark, with exact bytes and memcheck."""
from pathlib import Path
import fcntl
import hashlib
import json
import statistics
import subprocess
import sys
import time

H=Path.home();R=Path(__file__).resolve().parents[1]
D=H/'fleet-downloads/rtxpro-q8-duplex-fixture-20261004'
PY=H/'src/Strata/.venv/bin/python'

def save(p,data):
    q=p.with_suffix('.tmp');q.write_text(json.dumps(data,indent=2)+'\n');q.replace(p)

def worker(out):
    out.mkdir(parents=True,exist_ok=False)
    state={'started':time.time(),'source':(R/'source-commit.txt').read_text().strip(),'steps':[]}
    def run(name,args):
        with (out/(name+'.log')).open('w') as log:
            r=subprocess.run(list(map(str,args)),stdout=log,stderr=subprocess.STDOUT,timeout=900)
        state['steps'].append({'label':name,'args':list(map(str,args)),'exit':r.returncode})
        save(out/'result.json',state)
        if r.returncode:raise RuntimeError(name+' failed')
    try:
        binary=out/'duplex-fixture'
        run('compile',['/usr/local/cuda/bin/nvcc','-std=c++17','-O3','-arch=sm_120',
            '-I'+str(R/'include'),R/'tools/duplex_exchange_fixture.cu','-o',binary])
        state['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
        run('memcheck',['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','86',binary,'--quick'])
        run('benchmark',[binary])
        rows=[json.loads(x) for x in (out/'benchmark.log').read_text().splitlines() if x.startswith('{')]
        assert rows[-1].get('completed')
        samples=[x for x in rows if 'slots' in x]
        assert len(samples)==96 and all(x['exact'] for x in samples)
        comparisons=[]
        for n in (1,4,16,96):
            off=[x['milliseconds'] for x in samples if x['slots']==n and not x['duplex']]
            on=[x['milliseconds'] for x in samples if x['slots']==n and x['duplex']]
            a,b=statistics.median(off),statistics.median(on)
            comparisons.append({'slots':n,'sequential_median_ms':a,'duplex_median_ms':b,
                'median_latency_reduction_pct':100*(1-b/a),'speed_ratio':a/b,'repetitions':len(off),
                'sequential_min_ms':min(off),'duplex_min_ms':min(on)})
        state.update(completed=True,device=rows[0],samples=samples,comparisons=comparisons,
            scope='Isolated transfer fixture; not a model TPS or end-to-end speedup claim.')
    except BaseException as error:state['error']=repr(error);raise
    finally:state['finished']=time.time();save(out/'result.json',state)

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(Path(sys.argv[2]));return
    sys.path.insert(0,str(H/'fleet-downloads'));import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF=time.time()+24*3600;r=base.CgroupRun(D,(R/'source-commit.txt').read_text().strip())
    r.s.update(current='waiting for exclusive GPU',shutdown_afterwards=False);r.save()
    lock=(H/'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while True:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:r.check_time();time.sleep(5)
        step=r.gpu('duplex-fixture',[PY,Path(__file__),'--worker',D/'{attempt}'],{},timeout=1800)
        r.s['result']=str(D/step['label']/'result.json');r.save()
    except BaseException as error:r.finish(error);raise
    else:r.finish()

if __name__=='__main__':main()
