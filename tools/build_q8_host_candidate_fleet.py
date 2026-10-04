#!/usr/bin/env python3
"""Wait for the baseline, build the branch, validate the worker, then test it."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

H = Path.home()
R = Path(__file__).resolve().parents[1]
PY = H / 'src/Strata/.venv/bin/python'


def save(p, data):
    t = p.with_suffix('.tmp'); t.write_text(json.dumps(data, indent=2) + '\n'); t.replace(p)


def validate_fixture(plan):
    gate = plan.get('fixture_gate')
    if not gate:
        return
    artifact = Path(gate['result'])
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != gate['result_sha256']:
        raise RuntimeError('Fixture evidence changed')
    evidence = json.loads(artifact.read_text())
    if not evidence.get('completed') or evidence.get('source') != gate['source']:
        raise RuntimeError('Fixture did not pass on the expected source')
    steps = {s['label']: s['exit'] for s in evidence['steps']}
    if any(steps.get(k) != 0 for k in ('compile', 'memcheck', 'benchmark')):
        raise RuntimeError('Fixture build, exact-copy benchmark or memory sanitizer failed')
    for name, expected in gate['source_sha256'].items():
        if hashlib.sha256((R / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Fixture-tested source changed: ' + name)


def build(out, q8_components=False):
    out.mkdir(parents=True, exist_ok=False)
    result = {'started': time.time(), 'steps': [], 'source': (R/'source-commit.txt').read_text().strip()}
    def run(name, cmd, required=True):
        started = time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            r = subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        result['steps'].append({'name':name, 'command':list(map(str,cmd)), 'exit':r.returncode,
                               'seconds':time.monotonic()-started})
        save(out/'result.json', result)
        if r.returncode and required: raise RuntimeError(name+' failed; see log')
        return r.returncode
    try:
        run('worker-sanitize-build', ['g++','-std=c++20','-pthread','-O1','-g','-fsanitize=address,undefined',
            '-fno-omit-frame-pointer','-I'+str(R/'include'),R/'tests/core/serial_worker_test.cpp',
            '-o',out/'worker-sanitize'])
        run('worker-sanitize', [out/'worker-sanitize'])
        run('worker-tsan-build', ['g++','-std=c++20','-pthread','-O1','-g','-fsanitize=thread',
            '-fno-omit-frame-pointer','-I'+str(R/'include'),R/'tests/core/serial_worker_test.cpp',
            '-o',out/'worker-tsan'])
        if run('worker-tsan', [out/'worker-tsan'], required=False):
            text = (out/'worker-tsan.log').read_text()
            if 'FATAL: ThreadSanitizer: unexpected memory mapping' not in text:
                raise RuntimeError('Worker ThreadSanitizer reported a failure')
            # Newer kernels can map DSOs into GCC TSan's shadow address range.
            # Change only this fixture process, never the system ASLR setting.
            run('worker-tsan-noaslr', ['setarch', os.uname().machine, '-R', out/'worker-tsan'])
            result['tsan_mapping_workaround'] = 'ASLR off for this sanitizer process only'
        ccache = shutil.which('ccache')
        launchers = []
        if ccache:
            # Scope path normalization to this build; share the user's cache across
            # exported worktrees without relaxing compiler/header invalidation.
            launcher = ';'.join([shutil.which('cmake'), '-E', 'env', 'CCACHE_BASEDIR='+str(R), ccache])
            launchers = ['-DCMAKE_'+lang+'_COMPILER_LAUNCHER='+launcher for lang in ('C','CXX','CUDA')]
            result['ccache'] = {'version':subprocess.check_output([ccache,'--version'],text=True).splitlines()[0],
                                'launcher':launcher}
            run('ccache-before', [ccache,'--show-stats','--verbose'])
        run('configure', ['cmake','-S',R,'-B',R/'build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc','-DCMAKE_CUDA_ARCHITECTURES=120',
            '-DSTRATA_ENABLE_CUDA=ON','-DSTRATA_ENABLE_HIP=OFF','-DSTRATA_NATIVE_EXPERTS=ON',
            '-DSTRATA_GGML_DIR='+str(H/'src/Strata/third_party/llama.cpp'),'-DSTRATA_MMQ_KQUANTS=ON',
            '-DSTRATA_FLEET_CUDA_TRACE=ON','-DSTRATA_BUILD_TESTS='+('ON' if q8_components else 'OFF'),
            '-DIQ_FIXTURE_PYTHON='+str(PY)]+launchers)
        targets=['strata']+(['iq_multi_parity'] if q8_components else [])
        run('build', ['cmake','--build',R/'build','--target',*targets,'-j','8'])
        if ccache:
            # Verify real C++ and CUDA objects are cached and restored byte-for-byte.
            def stats():
                return {k:int(v) for k,v in (line.split() for line in
                    subprocess.check_output([ccache,'--print-stats'],text=True).splitlines())}
            objects=[]
            for filename in ('generate.cpp.o','iq_kernels.cu.o'):
                matches=list((R/'build').rglob(filename))
                if len(matches)!=1:raise RuntimeError('Cannot identify cache probe object: '+filename)
                obj=matches[0];objects.append((obj,hashlib.sha256(obj.read_bytes()).hexdigest()))
            before=stats()
            for obj,_ in objects:obj.unlink()
            run('ccache-replay', ['cmake','--build',R/'build','--target',
                *[str(obj.relative_to(R/'build')) for obj,_ in objects],'-j','2'])
            after=stats()
            hits=sum(after.get(k,0)-before.get(k,0) for k in ('direct_cache_hit','preprocessed_cache_hit'))
            result['ccache']['probe']={'cache_hits':hits,'objects':[
                {'path':str(obj.relative_to(R/'build')),'sha256':digest,
                 'byte_identical':hashlib.sha256(obj.read_bytes()).hexdigest()==digest} for obj,digest in objects]}
            if hits<2 or not all(o['byte_identical'] for o in result['ccache']['probe']['objects']):
                raise RuntimeError('C++/CUDA cache verification failed')
            run('relink', ['cmake','--build',R/'build','--target','strata','-j','8'])
            run('ccache-after', [ccache,'--show-stats','--verbose'])
        result.update(completed=True,engine_sha256=hashlib.sha256((R/'build/strata').read_bytes()).hexdigest())
        if q8_components:
            result['fixture_sha256']=hashlib.sha256((R/'build/iq_multi_parity').read_bytes()).hexdigest()
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        result['finished']=time.time();save(out/'result.json',result)


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--build':
        build(Path(sys.argv[2]),'--q8-components' in sys.argv)
        return
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
        validate_fixture(plan)
        while not prior.exists() or not json.loads(prior.read_text()).get('finished'):
            r.check_time();time.sleep(5)
        if not json.loads(prior.read_text()).get('completed'):raise RuntimeError('Baseline failed; inspect before candidates')
        while True:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:r.check_time();time.sleep(5)
        build_args=[PY,Path(__file__),'--build',out/'{attempt}']
        if plan.get('q8_component_gate'):build_args.append('--q8-components')
        stage=r.gpu('build',build_args,{},timeout=2400)
        gate=json.loads((out/stage['label']/'result.json').read_text())
        if not gate.get('completed'):raise RuntimeError('Build or sanitizer gate failed')
        r.s['engine_sha256']=gate['engine_sha256'];r.save()
        if plan.get('q8_component_gate'):
            env={'STRATA_Q8_EXPERT_REUSE':'1'}
            r.gpu('q8-components',[R/'build/iq_multi_parity','--q8-experts','--bench','--mapped-bench'],env,timeout=600)
            r.gpu('q8-memcheck',['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck',
                '--error-exitcode','42',R/'build/iq_multi_parity','--q8-experts'],env,timeout=600)
            r.s['component_fixture_sha256']=gate['fixture_sha256'];r.save()
            if plan.get('tests_only'):
                r.finish()
                return
        step=r.gpu('candidate',[PY,R/'tools/run_q8_host_path_fleet.py','--worker',plan_path,out/'{attempt}'],{},timeout=6*3600)
        r.s['matrix']=str(out/step['label']/'matrix.json');r.save()
    except BaseException as error:r.finish(error);raise
    else:r.finish()


if __name__=='__main__':main()
