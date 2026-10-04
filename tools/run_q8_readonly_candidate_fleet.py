#!/usr/bin/env python3
"""Gated Q8 miss-cache/overlap build and GPU component checks on llm-60."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

H = Path.home()
R = Path(__file__).resolve().parents[1]
PY = H / 'src/Strata/.venv/bin/python'


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def gates(out):
    from build_q8_host_candidate_fleet import build
    out.mkdir(parents=True, exist_ok=False)
    state = dict(started=time.time(), steps=[], completed=False,
                 source=(R / 'source-commit.txt').read_text().strip())
    def run(label, args, env=None, expected=0):
        start = time.monotonic()
        environment = {k:v for k,v in os.environ.items() if k != 'STRATA_MISS_FETCH_BLOCKS'}
        environment.update(CCACHE_BASEDIR=str(R))
        environment.update(env or {})
        with (out / (label + '.log')).open('w') as log:
            p = subprocess.run(list(map(str,args)),stdout=log,stderr=subprocess.STDOUT,timeout=900,
                               env=environment)
        state['steps'].append(dict(label=label,command=list(map(str,args)),exit=p.returncode,
                                   environment=env or {},expected_exit=expected,
                                   seconds=time.monotonic()-start))
        save(out/'result.json',state)
        if p.returncode != expected:
            raise RuntimeError(label+' failed; inspect preserved log')
    try:
        nvcc = '/usr/local/cuda/bin/nvcc'
        for label,source in [('fixture','tools/readonly_miss_cache_fixture.cu'),
                             ('cache','src/kernels/cuda/readonly_miss_cache.cu'),
                             ('verify','src/kernels/cuda/verify_kernels.cu')]:
            run(label+'-compile',['ccache',nvcc,'-std=c++17','-O2','-lineinfo','-arch=sm_120',
                '-I'+str(R/'include'),'-c',R/source,'-o',out/(label+'.o')])
        run('fixture-link',[nvcc,out/'fixture.o',out/'cache.o',out/'verify.o','-o',out/'fixture'])
        run('fixture-default',[out/'fixture'])
        for blocks in (1,32,96,384):
            env={'STRATA_MISS_FETCH_BLOCKS':str(blocks)}
            label='fixture-blocks'+str(blocks)
            run(label,[out/'fixture'],env)
            text=(out/(label+'.log')).read_text()
            if f'strata miss fetch geometry: blocks={blocks} threads=256;' not in text:
                raise RuntimeError('Missing geometry activation: '+label)
        for blocks in (32,96,384):
            for sanitizer in ['memcheck','initcheck']:
                run(f'fixture-{sanitizer}-blocks{blocks}',
                    ['/usr/local/cuda/bin/compute-sanitizer','--tool',sanitizer,
                     '--error-exitcode','42',out/'fixture','--quick'],
                    {'STRATA_MISS_FETCH_BLOCKS':str(blocks)})
        for index,value in enumerate(('', '0', '-1', '4097', '32x')):
            label='invalid-geometry-'+str(index)
            run(label,[out/'fixture','--quick'],{'STRATA_MISS_FETCH_BLOCKS':value},expected=1)
            if 'must be an integer from 1 to 4096' not in (out/(label+'.log')).read_text():
                raise RuntimeError('Invalid geometry failed for an unexpected reason: '+label)
        build(out/'engine-build')
        state.update(completed=True,engine_sha256=hashlib.sha256((R/'build/strata').read_bytes()).hexdigest())
    except BaseException as error:
        state['error'] = repr(error)
        raise
    finally:
        state['finished'] = time.time()
        save(out/'result.json',state)


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--gates':
        gates(Path(sys.argv[2]));return
    plan_path = Path(sys.argv[1]).resolve()
    plan = json.loads(plan_path.read_text())
    out = Path(plan['output'])
    sys.path.insert(0,str(H/'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF = time.time()+12*3600
    source = (R/'source-commit.txt').read_text().strip()
    r = base.CgroupRun(out,source)
    r.s.update(current='waiting for GPU idle',shutdown_afterwards=False,
               operational_guard_not_user_deadline=True,
               cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF,datetime.timezone.utc).isoformat())
    r.save()
    lock = (H/'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while True:
            try:
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                r.check_time();time.sleep(5)
        step = r.gpu('readonly-gates',[PY,Path(__file__),'--gates',out/'{attempt}'],{},timeout=2400)
        gate = json.loads((out/step['label']/'result.json').read_text())
        if not gate.get('completed'):
            raise RuntimeError('Read-only miss-cache component gates failed')
        r.s.update(component_result=str(out/step['label']/'result.json'),engine_sha256=gate['engine_sha256'])
        r.save()
        if not plan.get('tests_only'):
            step = r.gpu('readonly-model',[PY,R/'tools/run_q8_host_path_fleet.py','--worker',
                         plan_path,out/'{attempt}'],{},timeout=6*3600)
            r.s['matrix'] = str(out/step['label']/'matrix.json');r.save()
    except BaseException as error:
        r.finish(error);raise
    else:
        r.finish()
    finally:
        fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()


if __name__=='__main__':main()
