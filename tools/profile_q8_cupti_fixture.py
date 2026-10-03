#!/usr/bin/env python3
"""Gate direct CUPTI collection on small/large static graphs and a traffic oracle."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

H = Path.home()
R = Path(__file__).resolve().parents[1]
D = H / 'fleet-downloads/rtxpro-q8-cupti-fixture-20261003'
PY = H / 'src/Strata/.venv/bin/python'
PRIOR = H / 'fleet-downloads/rtxpro-q8-capture-probe-20261003-r2/status.json'


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def worker(out):
    out.mkdir(parents=True, exist_ok=False)
    library = R / 'build-fleet/libcupti_decode_range.so'
    binary = R / 'build-fleet/cupti_graph_fixture'
    state = {'started': time.time(), 'source': (R / 'source-commit.txt').read_text().strip(),
             'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
             'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
             'static_graphs': True, 'automatic_replay': False, 'records': []}
    target = out / 'matrix.json'
    try:
        for shape, args in [('small', []), ('large-graph', ['--nodes', '4096']),
                            ('large-payload', ['--large-payload'])]:
            for profile in (False, True):
                label = shape + ('-profile' if profile else '-control')
                state['current'] = label; save(target, state)
                counters = out / (label + '.json')
                env = dict(os.environ)
                if profile:
                    env.update(LD_PRELOAD=str(library), STRATA_CUPTI_OUTPUT=str(counters))
                command = [str(binary), *args]
                with (out / (label + '.log')).open('w') as log:
                    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    timeout = False
                    try: process.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        timeout = True
                        os.killpg(process.pid, signal.SIGTERM)
                        try: process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL); process.wait()
                text = (out / (label + '.log')).read_text()
                rec = {'label': label, 'exit': process.returncode, 'timeout': timeout, 'command': command,
                       'passed': process.returncode == 0 and 'payload_correct=1 watchdog_interventions=0' in text}
                state['records'].append(rec); save(target, state)
                if not rec['passed']: raise RuntimeError(label + ' failed')
                if profile:
                    data = json.loads(counters.read_text())
                    rec['counters'] = data
                    if not data['completed'] or data['passes'] != 1 or data['ranges'] != 1 or data['dropped'] or data['replay']:
                        raise RuntimeError('Incomplete counter capture')
                    if shape == 'large-payload':
                        dram = sum(data['metrics'][key] for key in ('dram__bytes_op_read.sum', 'dram__bytes_op_write.sum'))
                        # Two profiled 512MiB read/modify/write kernels nominally
                        # move 2GiB. Allow the 128MiB L2, command traffic and
                        # deferred writeback, but reject missing/scaled counters.
                        rec['traffic_oracle_bytes'] = 2 * 2 * 512 * 2**20
                        rec['traffic_oracle_ratio'] = dram / rec['traffic_oracle_bytes']
                        if not 0.5 <= rec['traffic_oracle_ratio'] <= 1.5:
                            raise RuntimeError('DRAM traffic oracle outside declared cache-aware bounds')
                save(target, state)
        state['completed'] = True
    except BaseException as error:
        state['error'] = repr(error)
        raise
    finally:
        state['finished'] = time.time(); save(target, state)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2])); return
    sys.path.insert(0, str(H / 'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF = time.time() + 24 * 3600
    run = base.CgroupRun(D, (R / 'source-commit.txt').read_text().strip())
    run.s.update(shutdown_afterwards=False, current='waiting for Nsight probe to finish',
                 dependency=str(PRIOR), operational_guard_not_user_deadline=True,
                 cutoff_utc=datetime.datetime.fromtimestamp(base.wh.CUTOFF, datetime.timezone.utc).isoformat())
    run.save()
    lock = (H / 'fleet-downloads/.rtxpro-bandwidth.lock').open('a')
    try:
        while not PRIOR.exists() or not json.loads(PRIOR.read_text()).get('finished'):
            run.check_time(); time.sleep(5)
        build = R / 'build-fleet'; build.mkdir(exist_ok=True)
        commands = [
            ['g++', '-std=c++17', '-O2', '-fPIC', '-shared', '-pthread',
             '-I/usr/local/cuda-13.2/include', str(R / 'tools/cupti_decode_range.cpp'),
             '-L/usr/local/cuda-13.2/lib64', '-Wl,-rpath,/usr/local/cuda-13.2/lib64',
             '-lcupti', '-lcuda', '-lcudart', '-o', str(build / 'libcupti_decode_range.so')],
            ['/usr/local/cuda-13.2/bin/nvcc', '-std=c++17', '-O2', '-arch=sm_120',
             '--cudart', 'shared', '-Xcompiler', '-pthread', str(R / 'tools/cupti_graph_fixture.cu'),
             '-o', str(build / 'cupti_graph_fixture'), '-Xlinker', '-rpath',
             '-Xlinker', '/usr/local/cuda-13.2/lib64']]
        with (D / 'build.log').open('w') as log:
            for command in commands:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        while True:
            try: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except BlockingIOError: run.check_time(); time.sleep(5)
        step = run.gpu('cupti-fixture', [PY, Path(__file__), '--worker', D / '{attempt}'], {}, timeout=500)
        run.s['matrix'] = str(D / step['label'] / 'matrix.json'); run.save()
    except BaseException as error:
        run.finish(error); raise
    else:
        run.finish()


if __name__ == '__main__': main()
