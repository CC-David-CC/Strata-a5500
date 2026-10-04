#!/usr/bin/env python3
"""Private, sequential Q8 host-path trials. A plan records every intervention.

The existing fleet wrapper yields to foreign GPU work. Each arm starts a fresh
engine, keeps FP16 KV and native RoPE, and records token IDs, source/binary
hashes, placement and host timing. No profiled time is used as throughput.
"""
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
FROZEN = H / 'src/strata-q8-exchange-rotation-1a50d913'
FROZEN_SOURCE = '1a50d913bf910a1f63fbc1a0788a7083e3ca5f8c'
FROZEN_SHA = 'd14ed6b69a1814ce4b5c08932a47d6921a55fa0aa8dea50427ccf0782d1ad997'


def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.replace(path)


def option(args, key, value):
    if key in args:
        args[args.index(key) + 1] = str(value)
    else:
        args.extend([key, str(value)])


def worker(plan_path, out):
    plan = json.loads(plan_path.read_text())
    sys.path.insert(0, str(FROZEN / 'tools'))
    from configure_rtxpro import configure
    assert hashlib.sha256((FROZEN / 'build/strata').read_bytes()).hexdigest() == FROZEN_SHA
    out.mkdir(parents=True, exist_ok=False)
    state = dict(plan=plan, started=time.time(), records=[], completed=False)
    target = out / 'matrix.json'
    save(target, state)
    try:
        for trial in plan['trials']:
            label = trial['label']
            state['current'] = label
            engine = Path(trial.get('engine', str(FROZEN)))
            source = trial.get('source', FROZEN_SOURCE)
            cfg = configure({'weights': 'Q8_0', 'kv': 'fp16', 'load_projection': False},
                            engine, H, trial['input_tokens'] + 8192)
            cfg['env'].update(STRATA_PLE_PREFAULT_THREADS='8', STRATA_ADAPT_NOWAIT='0',
                              STRATA_EXCHANGE_ROTATE='1', STRATA_FLEET_PROFILE='0')
            cfg['env'].update(trial.get('env', {}))
            # Equal residency across modes/contexts isolates host-side changes;
            # 15,472 slots leave more room than the measured native 64K preset.
            option(cfg['args'], '--expert-cache', trial.get('expert_cache', 15472))
            for key, value in trial.get('options', {}).items():
                option(cfg['args'], key, value)
            config = out / (label + '-config.json')
            save(config, cfg)
            result_dir = out / label
            cmd = [PY, engine / 'tools/bench_mtp_modes.py', '--config', config,
                   '--output', result_dir, '--input-tokens', str(trial['input_tokens']),
                   '--output-tokens', str(trial.get('output_tokens', 1024)),
                   '--mode', trial['mtp'], '--suffix-draft', str(trial['suffix']),
                   '--verify-window', '8', '--mtp-window', '4', '--workload', 'long',
                   '--repetitions', str(trial.get('repetitions', 1)),
                   '--cases', *trial.get('cases', ['coding', 'editing']),
                   '--source-commit', source]
            record = dict(trial=trial, started=time.time(), command=list(map(str, cmd)),
                          engine_sha256=hashlib.sha256((engine / 'build/strata').read_bytes()).hexdigest())
            state['records'].append(record)
            save(target, state)
            with (out / (label + '.log')).open('w') as log:
                run = subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT,
                                     timeout=2400)
            record.update(exit=run.returncode, finished=time.time())
            result = result_dir / 'result.json'
            if result.exists():
                data = json.loads(result.read_text())
                record.update(prompt_sha256=data['prompt_sha256'], runs=data['runs'],
                              allocated_context=data['context_allocation'])
            engine_log = result_dir / ('engine-mtp-' + trial['mtp'] + '.log')
            if engine_log.exists():
                log = engine_log.read_text(errors='replace')
                record['diagnostics'] = [line for line in log.splitlines() if any(s in line for s in (
                    'decode timing:', 'host critical:', 'resident RAM:', 'expert cache auto',
                    'exchange buffer rotation', 'host memcpy bytes avoided', 'GPU stages',
                    'pool phases', 'RAM budget', 'cache complement ready', 'CPU pool:',
                    'PCIe', 'adaptive worker', 'resident RAM mode:', 'pinned'))]
                record['rotation_active'] = 'exchange buffer rotation enabled' in log
            save(target, state)
            if run.returncode:
                raise RuntimeError(label + ' failed; inspect preserved logs')
            if not record.get('rotation_active'):
                raise RuntimeError(label + ': ownership rotation did not activate')
            cases = [c for run in record['runs'] for c in run['cases']]
            if not cases or any(c['input_tokens'] != trial['input_tokens'] or
                                not c['output_tokens'] or c['timings']['file_blobs'] != 0
                                for c in cases):
                raise RuntimeError(label + ': missing output or unexpected file expert reads')
        state['completed'] = True
    except BaseException as error:
        state['error'] = repr(error)
        raise
    finally:
        state['finished'] = time.time()
        save(target, state)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    plan_path = Path(sys.argv[1]).resolve()
    plan = json.loads(plan_path.read_text())
    out = Path(plan['output'])
    sys.path.insert(0, str(H / 'fleet-downloads'))
    import run_q4_trace_1c0c2bb as base
    base.wh.CUTOFF = time.time() + 24 * 3600
    source = (R / 'source-commit.txt').read_text().strip()
    r = base.CgroupRun(out, source)
    r.s.update(shutdown_afterwards=False, plan=str(plan_path), current='waiting for GPU idle',
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
        step = r.gpu('host-path', [PY, Path(__file__), '--worker', plan_path, out / '{attempt}'],
                     {}, timeout=6 * 3600)
        r.s['matrix'] = str(out / step['label'] / 'matrix.json')
        r.save()
    except BaseException as error:
        r.finish(error)
        raise
    else:
        r.finish()


if __name__ == '__main__':
    main()
