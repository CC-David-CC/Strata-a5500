#!/usr/bin/env python3
"""Build and collect private Q8 ownership traces after the current fleet queue."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import sys
import time

H = Path.home()
R = Path(__file__).resolve().parents[1]
PY = H / 'src/Strata/.venv/bin/python'


def main():
    plan_path = Path(sys.argv[1]).resolve()
    plan = json.loads(plan_path.read_text())
    out = Path(plan['output'])
    sys.path.insert(0, str(H / 'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    from analyze_q8_retained_copies import analyze
    base.wh.CUTOFF = time.time() + 12 * 3600
    source = (R / 'source-commit.txt').read_text().strip()
    r = base.CgroupRun(out, source)
    r.s.update(current='waiting for idle GPU', shutdown_afterwards=False,
               operational_guard_not_user_deadline=True,
               cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF, datetime.timezone.utc).isoformat())
    r.save()
    lock = (H / 'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                r.check_time()
                time.sleep(5)
        build = r.gpu('trace-build', [PY, R / 'tools/build_q8_host_candidate_fleet.py',
                      '--build', out / '{attempt}'], {}, timeout=2400)
        gate = json.loads((out / build['label'] / 'result.json').read_text())
        if not gate.get('completed'):
            raise RuntimeError('Trace engine failed to build')
        actual = hashlib.sha256((R / 'build/strata').read_bytes()).hexdigest()
        if gate['engine_sha256'] != actual:
            raise RuntimeError('Trace binary differs from build result')
        r.s['engine_sha256'] = actual
        r.save()
        step = r.gpu('retained-trace', [PY, R / 'tools/run_q8_host_path_fleet.py',
                     '--worker', plan_path, out / '{attempt}'], {}, timeout=6 * 3600)
        matrix = out / step['label'] / 'matrix.json'
        r.s['matrix'] = str(matrix)
        r.save()
        data = json.loads(matrix.read_text())
        if not data.get('completed'):
            raise RuntimeError('Trace model suite failed')
        traces = []
        for record in data['records']:
            if record['engine_sha256'] != actual:
                raise RuntimeError('Trace suite used another engine')
            trial = record['trial']
            log = matrix.parent / trial['label'] / ('engine-mtp-' + trial['mtp'] + '.log')
            result = analyze(log)
            result['trial'] = trial
            result['comparisons'] = record.get('comparisons', [])
            traces.append(result)
        report = out / 'retained-copy-replay.json'
        report.write_text(json.dumps(dict(source=source, engine_sha256=actual,
                          completed=True, traces=traces), indent=2) + '\n')
        r.s['retained_copy_replay'] = str(report)
        r.save()
    except BaseException as error:
        r.finish(error)
        raise
    else:
        r.finish()
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


if __name__ == '__main__':
    main()
