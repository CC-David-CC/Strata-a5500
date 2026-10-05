"""Frozen build + exact component/model gates, then private Q8 initial screen."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tarfile
import time

root=Path.home()/'fleet-downloads/adaptation-pr904-20261005'
state={'phase':'starting','started_unix':time.time(),'commands':[]}
def save(**kw):
    state.update(kw);p=root/'status.tmp';p.write_text(json.dumps(state,indent=2)+'\n');p.replace(root/'status.json')
def run(label,args,env=None):
    save(phase=label);t=time.monotonic()
    with (root/(label+'.log')).open('x') as log:
        code=subprocess.run([str(x) for x in args],stdout=log,stderr=subprocess.STDOUT,env=env).returncode
    state['commands'].append({'label':label,'exit_code':code,'seconds':time.monotonic()-t});save()
    if code:raise RuntimeError(label+' failed: '+str(code))
try:
    save()
    source=root/'source';source.mkdir(exist_ok=False);build=root/'build'
    with tarfile.open(root/'source.tar.gz') as a:a.extractall(source,filter='data')
    env=dict(os.environ,CCACHE_BASEDIR=str(root),CCACHE_NOHASHDIR='true')
    run('configure',['cmake','-S',source,'-B',build,'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
        '-DSTRATA_ENABLE_CUDA=ON','-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc','-DCMAKE_CUDA_ARCHITECTURES=120',
        '-DCMAKE_CXX_COMPILER_LAUNCHER=ccache','-DCMAKE_CUDA_COMPILER_LAUNCHER=ccache','-DSTRATA_NATIVE_EXPERTS=ON',
        '-DSTRATA_BUILD_TESTS=ON','-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
        '-DSTRATA_GGML_DIR='+str(Path.home()/'fleet-downloads/strata-rotation-mvp-ab-20261004/ggml-3cf03257')],env)
    targets=['strata','pdl_parity','verify_batch_parity','mmvq_multi_parity','bf16_gemv_parity','kv_q4_parity',
             'file_expert_source_test','exchange_storage_test','duplex_exchange_test','layer_exchange_test']
    run('build',['cmake','--build',build,'--parallel','4','--target']+targets,env)
    save(engine_sha256=hashlib.file_digest((build/'strata').open('rb'),'sha256').hexdigest())
    old=Path.home()/'fleet-downloads/adaptation-no-rotation-20261005/build/strata'
    assert hashlib.file_digest(old.open('rb'),'sha256').hexdigest()=='b791cefe332068c0ab3dab8c7c429c9d16ac2347898754a371bc19a38163996a'
    lock=(Path.home()/'fleet-downloads/.rtxpro-bandwidth.lock').open('a+');save(phase='waiting_for_gpu_lock')
    fcntl.flock(lock,fcntl.LOCK_EX)
    args=['systemctl','show','strata-q8-lan.service','--property=ActiveState,UnitFileState,RefuseManualStart,MainPID']
    service=subprocess.check_output(args,text=True)
    assert all(x in service for x in ['ActiveState=inactive','UnitFileState=disabled','RefuseManualStart=yes','MainPID=0'])
    assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
    subprocess.run(['sudo','-n','prlimit','--pid',str(os.getpid()),'--memlock=unlimited:unlimited'],check=True)
    state['memlock']=resource.getrlimit(resource.RLIMIT_MEMLOCK)
    run('ctest',['ctest','--test-dir',build,'-R','^(pdl_parity|verify_batch_parity|mmvq_multi_parity|bf16_gemv_parity|kv_q4_parity|file_expert_source_test|exchange_storage_test|duplex_exchange_test|layer_exchange_test)$','--output-on-failure'])
    run('pdl-single-edge',[build/'pdl_parity'],dict(os.environ,STRATA_DF_PDL='2'))
    for fixture in ['pdl_parity','verify_batch_parity']:
        run('memcheck-'+fixture,['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','86',build/fixture])
    py=Path.home()/'src/Strata/.venv/bin/python'
    for name in ['q2-gate','q8-screen']:
        run(name,[py,'-u',root/'bench_combined.py',root/(name+'-plan.json'),root/name])
    assert subprocess.check_output(args,text=True)==service
    save(phase='complete',completed=True,finished_unix=time.time())
except BaseException as e:
    save(phase='failed',error=repr(e),finished_unix=time.time());raise
