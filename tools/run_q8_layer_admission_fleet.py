#!/usr/bin/env python3
"""Gate per-layer Q8 admission on byte/ownership/state checks before throughput."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

H=Path.home()
R=Path(__file__).resolve().parents[1]
PY=H/'src/Strata/.venv/bin/python'

def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)

def gates(out):
    from build_q8_host_candidate_fleet import build
    out.mkdir(parents=True,exist_ok=False)
    state=dict(started=time.time(),source=(R/'source-commit.txt').read_text().strip(),steps=[],completed=False)
    def run(label,args):
        start=time.monotonic()
        env=dict(os.environ,CCACHE_BASEDIR=str(R))
        with (out/(label+'.log')).open('w') as log:
            p=subprocess.run(list(map(str,args)),env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        state['steps'].append(dict(label=label,command=list(map(str,args)),exit=p.returncode,seconds=time.monotonic()-start))
        save(out/'result.json',state)
        if p.returncode:raise RuntimeError(label+' failed; preserved log required')
    try:
        for mode,flags in [('asan',['-fsanitize=address,undefined']),('tsan',['-fsanitize=thread'])]:
            run('ownership-'+mode+'-compile',['g++','-std=c++20','-pthread','-O1','-g',
                '-fno-omit-frame-pointer',*flags,'-I'+str(R/'include'),
                R/'tests/core/exchange_storage_test.cpp','-o',out/('ownership-'+mode)])
            run('ownership-'+mode,(['setarch',os.uname().machine,'-R'] if mode=='tsan' else [])+[out/('ownership-'+mode)])
        run('layer-fixture-compile',['ccache','/usr/local/cuda/bin/nvcc','-std=c++17','-O2','-lineinfo',
            '-arch=sm_120','-Xcompiler=-pthread','-I'+str(R/'include'),R/'tools/layer_exchange_fixture.cu',
            '-o',out/'layer-fixture'])
        run('layer-fixture',[out/'layer-fixture'])
        for kind in ('memcheck','initcheck'):
            run('layer-'+kind,['/usr/local/cuda/bin/compute-sanitizer','--tool',kind,
                '--error-exitcode','42',out/'layer-fixture'])
        # The optional event field must retain the original no-event transfer path.
        run('duplex-fixture-compile',['ccache','/usr/local/cuda/bin/nvcc','-std=c++17','-O2',
            '-arch=sm_120','-I'+str(R/'include'),R/'tools/duplex_exchange_fixture.cu','-o',out/'duplex-fixture'])
        run('duplex-fixture',[out/'duplex-fixture','--quick'])
        build(out/'engine-build')
        state.update(completed=True,engine_sha256=hashlib.sha256((R/'build/strata').read_bytes()).hexdigest())
    except BaseException as error:
        state['error']=repr(error);raise
    finally:
        state['finished']=time.time();save(out/'result.json',state)

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--gates':
        gates(Path(sys.argv[2]));return
    plan_path=Path(sys.argv[1]).resolve();plan=json.loads(plan_path.read_text())
    out=Path(plan['output'])
    sys.path.insert(0,str(H/'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF=time.time()+12*3600
    r=base.CgroupRun(out,(R/'source-commit.txt').read_text().strip())
    r.s.update(current='waiting for GPU idle',shutdown_afterwards=False,
        operational_guard_not_user_deadline=True,
        cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF,datetime.timezone.utc).isoformat());r.save()
    lock=(H/'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while True:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:r.check_time();time.sleep(5)
        step=r.gpu('layer-gates',[PY,Path(__file__),'--gates',out/'{attempt}'],{},timeout=3000)
        gate_path=out/step['label']/'result.json'
        gate=json.loads(gate_path.read_text())
        if not gate.get('completed'):raise RuntimeError('Per-layer component gate incomplete')
        r.s.update(component_result=str(gate_path),engine_sha256=gate['engine_sha256']);r.save()
        lifecycle=dict(plan['lifecycle'],component_status=str(gate_path),engine=str(R))
        lifecycle_plan=out/'lifecycle-plan.json';save(lifecycle_plan,lifecycle)
        step=r.gpu('layer-lifecycle',[PY,R/'tools/test_q8_readonly_lifecycle.py','--plan',
            lifecycle_plan,'--output',out/'{attempt}'],{},timeout=7200)
        life_path=out/step['label']/'result.json';life=json.loads(life_path.read_text())
        if not life.get('completed') or not all(a.get('passed') for a in life['arms']):
            raise RuntimeError('Per-layer lifecycle gate failed')
        r.s['lifecycle']=str(life_path);r.save()
        step=r.gpu('layer-model',[PY,R/'tools/run_q8_host_path_fleet.py','--worker',plan_path,
            out/'{attempt}'],{},timeout=6*3600)
        r.s['matrix']=str(out/step['label']/'matrix.json');r.save()
    except BaseException as error:
        r.finish(error);raise
    else:r.finish()
    finally:
        fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()

if __name__=='__main__':main()
