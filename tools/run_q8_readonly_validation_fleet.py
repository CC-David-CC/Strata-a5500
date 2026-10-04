#!/usr/bin/env python3
"""Validate the component-tested Q8 cache binary, then benchmark the same binary."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import sys
import time

H=Path.home()
R=Path(__file__).resolve().parents[1]
PY=H/'src/Strata/.venv/bin/python'


def main():
    plan_path=Path(sys.argv[1]).resolve()
    plan=json.loads(plan_path.read_text())
    out=Path(plan['output']);engine=Path(plan['engine'])
    gate=json.loads(Path(plan['component_status']).read_text())
    if not gate.get('completed'):
        raise RuntimeError('Component gates have not completed successfully')
    digest=hashlib.sha256((engine/'build/strata').read_bytes()).hexdigest()
    if digest!=gate['engine_sha256']:
        raise RuntimeError('Component-tested binary changed')
    component=json.loads(Path(gate['component_result']).read_text())
    source=(engine/'source-commit.txt').read_text().strip()
    if component['source']!=source or not component.get('completed'):
        raise RuntimeError('Component source/gates mismatch')
    for trial in plan['trials']:
        if Path(trial['engine'])!=engine or trial['source']!=source:
            raise RuntimeError('Benchmark arm uses another source/engine')
    sys.path.insert(0,str(H/'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF=time.time()+12*3600
    r=base.CgroupRun(out,(R/'source-commit.txt').read_text().strip())
    r.s.update(current='waiting for GPU idle',shutdown_afterwards=False,engine_sha256=digest,
        engine_source=source,plan=str(plan_path),operational_guard_not_user_deadline=True,
        cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF,datetime.timezone.utc).isoformat())
    r.save()
    lock=(H/'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while True:
            try:
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                r.check_time();time.sleep(5)
        step=r.gpu('readonly-lifecycle',[PY,R/'tools/test_q8_readonly_lifecycle.py',
                   '--plan',plan_path,'--output',out/'{attempt}'],{},timeout=3600)
        lifecycle=out/step['label']/'result.json'
        life=json.loads(lifecycle.read_text())
        r.s['lifecycle']=str(lifecycle);r.save()
        if not life.get('completed') or life['engine_sha256']!=digest:
            raise RuntimeError('Lifecycle gate failed or used another binary')
        step=r.gpu('readonly-model',[PY,R/'tools/run_q8_host_path_fleet.py','--worker',
                   plan_path,out/'{attempt}'],{},timeout=6*3600)
        matrix=out/step['label']/'matrix.json'
        r.s['matrix']=str(matrix);r.save()
        data=json.loads(matrix.read_text())
        if not data.get('completed') or any(rec['engine_sha256']!=digest for rec in data['records']):
            raise RuntimeError('Model gate failed or used another binary')
    except BaseException as error:
        r.finish(error);raise
    else:
        r.finish()
    finally:
        fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()


if __name__=='__main__':main()
