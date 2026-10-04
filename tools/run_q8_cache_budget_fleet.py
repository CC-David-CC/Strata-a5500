#!/usr/bin/env python3
"""Build an unchanged engine, gate16-way lifecycle, compare uses of spare VRAM."""
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


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def build_gate(plan,out):
    from build_q8_host_candidate_fleet import build
    out.mkdir(parents=True,exist_ok=False)
    evidence=Path(plan['prior_component_gate'])
    if hashlib.sha256(evidence.read_bytes()).hexdigest()!=plan['prior_component_sha256']:
        raise RuntimeError('Earlier full-byte/sanitizer evidence changed')
    prior=json.loads(evidence.read_text())
    if (not prior.get('completed') or prior.get('engine_sha256')!=plan['expected_engine_sha256']
            or len(prior.get('capacity_full_blob_passes',[]))!=4
            or any(s['exit']!=s['expected_exit'] for s in prior['steps'])):
        raise RuntimeError('Earlier capacity component gate is incomplete')
    build(out/'engine-build')
    result=json.loads((out/'engine-build/result.json').read_text())
    if not result.get('completed') or result['engine_sha256']!=plan['expected_engine_sha256']:
        raise RuntimeError('Configuration branch changed the tested engine bytes')
    save(out/'result.json',dict(completed=True,source=(R/'source-commit.txt').read_text().strip(),
        engine_sha256=result['engine_sha256'],prior_component_gate=str(evidence),
        prior_component_sha256=plan['prior_component_sha256'],
        interpretation='Fresh branch build is byte-identical to the full-byte/sanitizer-tested capacity engine.'))


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--build':
        build_gate(json.loads(Path(sys.argv[2]).read_text()),Path(sys.argv[3]));return
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
        step=r.gpu('budget-build',[PY,Path(__file__),'--build',plan_path,out/'{attempt}'],{},timeout=3000)
        gate=out/step['label']/'result.json'
        r.s['build_gate']=str(gate);r.save()
        lifecycle=dict(plan['lifecycle'],component_status=str(gate),engine=str(R))
        lifecycle_plan=out/'lifecycle-plan.json';save(lifecycle_plan,lifecycle)
        step=r.gpu('budget-lifecycle',[PY,R/'tools/test_q8_readonly_lifecycle.py','--plan',
            lifecycle_plan,'--output',out/'{attempt}'],{},timeout=7200)
        life_path=out/step['label']/'result.json';life=json.loads(life_path.read_text())
        if not life.get('completed') or not all(a.get('passed') for a in life['arms']):
            raise RuntimeError('16-way normal/STOP/checkpoint lifecycle gate failed')
        r.s['lifecycle']=str(life_path);r.save()
        step=r.gpu('budget-model',[PY,R/'tools/run_q8_host_path_fleet.py','--worker',plan_path,
            out/'{attempt}'],{},timeout=6*3600)
        r.s['matrix']=str(out/step['label']/'matrix.json');r.save()
    except BaseException as error:
        r.finish(error);raise
    else:r.finish()
    finally:
        fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()


if __name__=='__main__':main()
