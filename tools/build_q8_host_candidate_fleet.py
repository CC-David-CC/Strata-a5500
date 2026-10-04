#!/usr/bin/env python3
"""Wait for the baseline, build the branch, validate the worker, then test it."""
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


def save(p, data):
    t = p.with_suffix('.tmp'); t.write_text(json.dumps(data, indent=2) + '\n'); t.replace(p)


def build(out):
    out.mkdir(parents=True, exist_ok=False)
    result = {'started': time.time(), 'steps': [], 'source': (R/'source-commit.txt').read_text().strip()}
    def run(name, cmd):
        with (out/(name+'.log')).open('w') as log:
            r = subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        result['steps'].append({'name':name, 'command':list(map(str,cmd)), 'exit':r.returncode})
        save(out/'result.json', result)
        if r.returncode: raise RuntimeError(name+' failed; see log')
    try:
        run('worker-sanitize-build', ['g++','-std=c++20','-pthread','-O1','-g','-fsanitize=address,undefined',
            '-fno-omit-frame-pointer','-I'+str(R/'include'),R/'tests/core/serial_worker_test.cpp',
            '-o',out/'worker-sanitize'])
        run('worker-sanitize', [out/'worker-sanitize'])
        run('worker-tsan-build', ['g++','-std=c++20','-pthread','-O1','-g','-fsanitize=thread',
            '-fno-omit-frame-pointer','-I'+str(R/'include'),R/'tests/core/serial_worker_test.cpp',
            '-o',out/'worker-tsan'])
        run('worker-tsan', [out/'worker-tsan'])
        run('configure', ['cmake','-S',R,'-B',R/'build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc','-DCMAKE_CUDA_ARCHITECTURES=120',
            '-DSTRATA_ENABLE_CUDA=ON','-DSTRATA_ENABLE_HIP=OFF','-DSTRATA_NATIVE_EXPERTS=ON',
            '-DSTRATA_GGML_DIR='+str(H/'src/Strata/third_party/llama.cpp'),'-DSTRATA_MMQ_KQUANTS=ON',
            '-DSTRATA_FLEET_CUDA_TRACE=ON','-DSTRATA_BUILD_TESTS=OFF'])
        run('build', ['cmake','--build',R/'build','--target','strata','-j','8'])
        result.update(completed=True,engine_sha256=hashlib.sha256((R/'build/strata').read_bytes()).hexdigest())
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        result['finished']=time.time();save(out/'result.json',result)


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--build':build(Path(sys.argv[2]));return
    plan_path=Path(sys.argv[1]).resolve();plan=json.loads(plan_path.read_text())
    sys.path.insert(0,str(H/'fleet-downloads'));import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF=time.time()+24*3600
    source=(R/'source-commit.txt').read_text().strip();out=Path(plan['output'])
    r=base.CgroupRun(out,source)
    prior=H/'fleet-downloads/rtxpro-q8-host-baseline-20261004/status.json'
    r.s.update(current='waiting for baseline completion',dependency=str(prior),shutdown_afterwards=False,
               cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF,datetime.timezone.utc).isoformat())
    r.save();lock=(H/'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while not prior.exists() or not json.loads(prior.read_text()).get('finished'):
            r.check_time();time.sleep(5)
        if not json.loads(prior.read_text()).get('completed'):raise RuntimeError('Baseline failed; inspect before candidates')
        while True:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:r.check_time();time.sleep(5)
        stage=r.gpu('build',[PY,Path(__file__),'--build',out/'{attempt}'],{},timeout=2400)
        gate=json.loads((out/stage['label']/'result.json').read_text())
        if not gate.get('completed'):raise RuntimeError('Build or sanitizer gate failed')
        r.s['engine_sha256']=gate['engine_sha256'];r.save()
        step=r.gpu('candidate',[PY,R/'tools/run_q8_host_path_fleet.py','--worker',plan_path,out/'{attempt}'],{},timeout=6*3600)
        r.s['matrix']=str(out/step['label']/'matrix.json');r.save()
    except BaseException as error:r.finish(error);raise
    else:r.finish()


if __name__=='__main__':main()
