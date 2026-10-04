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
import re
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
    references = {}
    if plan.get('reference_status'):
        status = json.loads(Path(plan['reference_status']).read_text())
        if not status.get('completed'):
            raise RuntimeError('Reference suite did not complete')
        reference = json.loads(Path(status['matrix']).read_text())
        references = {r['trial']['label']: r for r in reference['records']}
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
            if trial.get('expected_engine_info'):
                cfg['benchmark_expected_engine_info'] = trial['expected_engine_info']
                cfg['benchmark_required_startup_patterns'] = trial.get('required_startup_patterns', [])
            config = out / (label + '-config.json')
            save(config, cfg)
            result_dir = out / label
            benchmark = Path(trial.get('benchmark_script', engine / 'tools/bench_mtp_modes.py'))
            cmd = [PY, benchmark, '--config', config,
                   '--output', result_dir, '--input-tokens', str(trial['input_tokens']),
                   '--output-tokens', str(trial.get('output_tokens', 1024)),
                   '--mode', trial['mtp'], '--suffix-draft', str(trial['suffix']),
                   '--verify-window', '8', '--mtp-window', '4', '--workload', 'long',
                   '--repetitions', str(trial.get('repetitions', 1)),
                   '--cases', *trial.get('cases', ['coding', 'editing']),
                   '--source-commit', source]
            record = dict(trial=trial, started=time.time(), command=list(map(str, cmd)),
                          benchmark_sha256=hashlib.sha256(benchmark.read_bytes()).hexdigest(),
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
                    'decode timing:', 'decode traffic:', 'host critical:', 'resident RAM:', 'expert cache auto',
                    'exchange buffer rotation', 'host memcpy bytes avoided', 'GPU stages',
                    'pool phases', 'RAM budget', 'cache complement ready', 'CPU pool:',
                    'PCIe', 'adaptive worker', 'exchange duplex:', 'resident RAM mode:', 'pinned',
                    'readonly miss cache:', 'miss fetch overlap:', 'miss fetch geometry:', 'PLE startup',
                    'miss cache tag snapshot:', 'GPU refills:'))]
                record['rotation_active'] = 'exchange buffer rotation enabled' in log
                record['duplex_active'] = 'strata exchange duplex: enabled,' in log
                record['duplex_swaps'] = sum(map(int, re.findall(r'\bduplex_swaps (\d+)', log)))
                record['miss_cache_active'] = 'strata readonly miss cache: enabled,' in log
                record['miss_overlap_active'] = 'strata miss fetch overlap: enabled;' in log
                record['miss_fetch_blocks'] = list(map(int,re.findall(r'strata miss fetch geometry: blocks=(\d+) threads=256;',log)))
                record['miss_cache_reports'] = [dict(zip(('groups','hits','uploads','bypasses','avoided_upload_bytes','uploaded_bytes'),map(int,m)))
                    for m in re.findall(r'strata readonly miss cache: cumulative groups=(\d+) hits=(\d+) uploads=(\d+) bypasses=(\d+) avoided_upload_bytes=(\d+) uploaded_bytes=(\d+)',log)]
                record['tag_snapshot_reports'] = [dict(zip(('generations','bytes'),map(int,m)))
                    for m in re.findall(r' tag_snapshots=(\d+) tag_snapshot_bytes=(\d+)',log)]
                record['gpu_refill_reports'] = [dict(zip(('d2d_bytes','refills'),map(int,m)))
                    for m in re.findall(r'strata GPU refills: D2D_bytes (\d+) D2D_refills (\d+);',log)]
                record['primary_transfer_reports'] = [dict(zip(('d2h_bytes','h2d_bytes','swaps','duplex_swaps'),map(int,m)))
                    for m in re.findall(r'; D2H_bytes (\d+) H2D_bytes (\d+) swaps (\d+) duplex_swaps (\d+);',log)]
                record['gpu_refill_active'] = 'strata GPU refills: enabled;' in log
                record['tag_snapshot_active'] = 'strata miss cache tag snapshot: enabled,' in log
            save(target, state)
            if run.returncode:
                raise RuntimeError(label + ' failed; inspect preserved logs')
            if trial.get('expected_engine_info') and any(
                    not v.get('startup_precondition', {}).get('passed') for v in record['runs']):
                raise RuntimeError(label + ': required benchmark startup precondition was not checked')
            if not record.get('rotation_active'):
                raise RuntimeError(label + ': ownership rotation did not activate')
            cache_ways = int(trial.get('env', {}).get('STRATA_Q8_MISS_CACHE_WAYS','0'))
            fetch_blocks = trial.get('env', {}).get('STRATA_MISS_FETCH_BLOCKS')
            if fetch_blocks is not None and (not record.get('miss_fetch_blocks') or
                                             set(record['miss_fetch_blocks']) != {int(fetch_blocks)}):
                raise RuntimeError(label + ': miss-fetch geometry did not activate')
            if trial.get('env', {}).get('STRATA_Q8_MISS_FETCH_OVERLAP') == '1' and not record.get('miss_overlap_active'):
                raise RuntimeError(label + ': miss-fetch overlap did not activate')
            if cache_ways and (not record.get('miss_cache_active') or not record.get('miss_cache_reports')):
                raise RuntimeError(label + ': read-only miss cache did not activate/report')
            for report in record.get('miss_cache_reports',[]):
                if report['groups'] != report['hits'] + report['uploads'] or report['bypasses'] > report['uploads']:
                    raise RuntimeError(label + ': miss cache accounting inconsistent')
            if trial.get('env', {}).get('STRATA_EXCHANGE_DUPLEX') == '1' and (
                    not record.get('duplex_active') or not record.get('duplex_swaps')):
                raise RuntimeError(label + ': duplex copies did not activate; inspect fallback before timing claims')
            cases = [c for run in record['runs'] for c in run['cases']]
            if not cases or any(c['input_tokens'] != trial['input_tokens'] or
                                c['output_tokens'] != trial.get('output_tokens', 1024) or c['timings']['file_blobs'] != 0
                                for c in cases):
                raise RuntimeError(label + ': missing output or unexpected file expert reads')
            # These guards are opt-in so older benchmark exports remain readable.
            if trial.get('check_refill_counters'):
                snap = trial['env'].get('STRATA_Q8_CACHE_TAG_SNAPSHOT') == '1'
                refill = trial['env'].get('STRATA_Q8_GPU_REFILL') == '1'
                if record.get('tag_snapshot_active') != snap or record.get('gpu_refill_active') != refill:
                    raise RuntimeError(label + ': snapshot/refill option did not activate as requested')
                for key in ('tag_snapshot_reports','gpu_refill_reports','primary_transfer_reports'):
                    if len(record.get(key,[])) != len(cases):
                        raise RuntimeError(label + ': missing per-request '+key)
                for s,d,p in zip(record['tag_snapshot_reports'],record['gpu_refill_reports'],record['primary_transfer_reports']):
                    if (s['generations'] > 0) != snap or s['bytes'] != s['generations']*48*cache_ways*4:
                        raise RuntimeError(label + ': invalid snapshot generation/byte accounting')
                    if (d['refills'] > 0) != refill or d['d2d_bytes'] != d['refills']*5222400:
                        raise RuntimeError(label + ': expected GPU refills were absent or inconsistent')
                    if p['d2h_bytes'] != p['h2d_bytes'] + d['d2d_bytes']:
                        raise RuntimeError(label + ': primary victim/refill byte accounting differs')
            if trial.get('reference_label'):
                ref = references[trial['reference_label']]
                if ref['prompt_sha256'] != record['prompt_sha256']:
                    raise RuntimeError(label + ': reference prompt differs')
                old_cases = {(c['task'], c['repetition']): c for v in ref['runs'] for c in v['cases']}
                comparisons = []
                for case in cases:
                    old = old_cases[(case['task'], case['repetition'])]
                    a, b = old['token_ids'], case['token_ids']
                    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                                 None if len(a) == len(b) else min(len(a), len(b)))
                    keys = ('generated', 'drafts_accepted', 'drafts_offered', 'hits', 'lookups',
                            'ram_blobs', 'file_blobs', 'file_mb', 'prompt_read')
                    work = {k: [old['timings'].get(k), case['timings'].get(k)]
                            for k in keys if old['timings'].get(k) != case['timings'].get(k)}
                    comparisons.append({'task': case['task'], 'reference_label': trial['reference_label'],
                        'first_token_difference': first, 'work_differences': work,
                        'reference_tps': old['decode_tps'], 'candidate_tps': case['decode_tps'],
                        'decode_gain_pct': 100 * (case['decode_tps'] / old['decode_tps'] - 1),
                        'effective_gain_pct': 100 * (case['effective_output_tps'] / old['effective_output_tps'] - 1)})
                record['comparisons'] = comparisons
                save(target, state)
                if trial.get('require_exact') and any(c['first_token_difference'] is not None or
                                                     c['work_differences'] for c in comparisons):
                    raise RuntimeError(label + ': default-off parity gate failed')
                if trial.get('check_refill_counters') and trial.get('require_exact') and ref.get('primary_transfer_reports'):
                    oldp,newp = ref['primary_transfer_reports'],record['primary_transfer_reports']
                    if len(oldp) != len(newp) or any(any(a[k] != b[k] for k in ('d2h_bytes','swaps','duplex_swaps'))
                                                   for a,b in zip(oldp,newp)):
                        raise RuntimeError(label + ': refill changed primary exchanges')
            # Later arms may use a fresh, same-binary control from this matrix.
            # Retain the declared external reference for the first control.
            references[label] = record
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
