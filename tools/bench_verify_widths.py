#!/usr/bin/env python3
"""Measure real proposal paths and an explicitly non-deployable perfect-proposal control.

The manifest names a frozen completed benchmark and its prompt files. Every
answer must match the saved answer, so an accidentally easier/shorter request
cannot become a throughput gain. GPU isolation belongs to the fleet runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

PATHS = {'serial': (False, 0), 'mtp': (True, 0), 'ngram': (False, 3),
         'mtp-ngram': (True, 3), 'oracle': (False, 0)}
STATE_FIELDS = ('L', 'gdn', 'ple', 'tail', 'pooled', 'kv', 'ple_prev')


def digest(value):
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def request_limit(path, budget, expected_count):
    # The perfect predictor knows the EOS location as well as its token. Trim
    # its final window at that location, rather than proposing padding past EOS
    # and mistaking the discarded positions for incorrect proposals. Real
    # predictors retain the original requested budget and natural stopping.
    return min(budget, expected_count) if path == 'oracle' else budget


def read_reference(path):
    data = json.loads(path.read_text())
    cases = {}
    for run in data['runs']:
        for case in run['cases']:
            name = case['task']
            if name in cases and cases[name]['token_ids'] != case['token_ids']:
                raise ValueError('Frozen reference contains different answers for ' + name)
            cases[name] = case
    return cases


def parse_histogram(log):
    found = re.findall(r'WINDOW_HIST widths=([\d:,]+) committed=([\d:,]+)', log)
    if len(found) != 1:
        raise ValueError(f'Expected one width histogram, got {len(found)}')
    return [{int(k): int(v) for k, v in (item.split(':') for item in part.split(','))}
            for part in found[0]]


def validate_observation(job, tokens, expected, timings, widths, committed):
    if tokens != expected:
        first = next((i for i, (a, b) in enumerate(zip(tokens, expected)) if a != b),
                     min(len(tokens), len(expected)))
        raise ValueError(f'Token/reference mismatch at {first}: actual={len(tokens)} expected={len(expected)}')
    if timings.get('reused', 0):
        raise ValueError('A fresh prompt unexpectedly reused cached state')
    if sum(t * n for t, n in committed.items()) != len(tokens):
        raise ValueError('Committed histogram does not account for every emitted token')
    if sum(widths.values()) != sum(committed.values()):
        raise ValueError('Width and commit histogram window counts differ')
    if any(n and t > job['width'] for t, n in widths.items()):
        raise ValueError('Requested width cap was exceeded')
    if job['path'] == 'oracle' and timings['drafts_accepted'] != timings['drafts_offered']:
        raise ValueError('Perfect-proposal control rejected a proposal')


def run(manifest_path, output):
    from serve.server import StrataEngine, child_env
    from bench_mtp_modes import set_option
    manifest = json.loads(manifest_path.read_text())
    cfg = json.loads(Path(manifest['config']).read_text())
    reference_path = Path(manifest['reference_result'])
    reference = read_reference(reference_path)
    allocation = manifest.get('allocation', 8)
    output.mkdir(parents=True, exist_ok=False)
    status = {'manifest': manifest, 'started': time.time(), 'records': [],
              'engine_sha256': hashlib.sha256(Path(cfg['exe']).read_bytes()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'reference_sha256': hashlib.sha256(reference_path.read_bytes()).hexdigest(),
              'scope': 'Q4; oracle is verification capacity with known answers, not real n-gram performance'}

    def save():
        p = output / 'widths.json'
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(status, indent=2))
        tmp.replace(p)

    save()
    try:
        for index, job in enumerate(manifest['jobs']):
            width = job['width']
            path = job['path']
            if path not in PATHS or not 1 <= width <= allocation:
                raise ValueError('Invalid path or width')
            if path == 'serial' and width != 1:
                raise ValueError('Serial is a T=1 control')
            mtp, suffix = PATHS[path]
            record = {**job, 'results': [], 'started': time.time()}
            status['records'].append(record)
            for name in job['cases']:
                label = f'{index:03d}-{path}-t{width}-{job.get("repeat", "r1")}-{name}'
                status['current'] = label
                save()
                d = output / label
                d.mkdir()
                prompt_path = reference_path.parent / (name + '.tokens.json')
                ids = json.loads(prompt_path.read_text())
                if len(ids) != manifest.get('input_tokens', 65536):
                    raise ValueError('Frozen input does not have the requested length')
                maximum = job.get('output_tokens', 4096)
                expected = reference[name]['token_ids'][:maximum]
                if not expected:
                    raise ValueError('Empty reference')
                if len(expected) < maximum and not reference[name].get('natural_stop'):
                    raise ValueError('Reference is too short and did not stop naturally')
                args = list(cfg['args'])
                for key, value in [('--spec', allocation), ('--mtp-max-t', width),
                                   ('--suffix-draft', suffix), ('--spec-min-p', job.get('mtp_min_p', 0.5)),
                                   ('--prompt-cache', 0), ('--conversation-cache-mib', 0)]:
                    set_option(args, key, value)
                if not mtp:
                    set_option(args, '--mtp', None)
                env = child_env(cfg)
                # Explicitly clear controls from earlier experiments.
                for key in ['STRATA_STATE_HASH', 'STRATA_VERIFY_PROFILE', 'STRATA_VERIFY_REJECT_DEPTH',
                            'STRATA_VERIFY_ORACLE_WINDOW', 'STRATA_TRACE', 'STRATA_VERIFY_DEBUG']:
                    env.pop(key, None)
                env.update(STRATA_DIAG_WINDOW_LIMIT=str(width), STRATA_WINDOW_HISTOGRAM='1',
                           STRATA_VERIFY_ORACLE_LOG='0', STRATA_GRAPH_CAPTURE_LOG='1',
                           STRATA_DECODE_TIMING='1',
                           STRATA_PREPARE_VERIFY_GRAPHS=str(int(job.get('prepare', True))),
                           STRATA_PREPARE_MTP_GRAPHS=str(int(job.get('prepare', True))))
                if job.get('state_hash'):
                    env['STRATA_STATE_HASH'] = '1'
                    for key, value in [('--prompt-cache', 1), ('--prompt-cache-every', 0),
                                       ('--prompt-cache-root', 0), ('--turn-token', -1)]:
                        set_option(args, key, value)
                if job.get('trace'):
                    env['STRATA_TRACE'] = '1'
                    env['STRATA_VERIFY_DEBUG'] = '1'
                if path == 'oracle':
                    oracle = d / 'known-answer.tokens.txt'
                    # Padding is never committed: expected ends in natural EOS or exactly at the output cap.
                    oracle.write_text(','.join(map(str, expected + [0] * (maximum - len(expected)))))
                    set_option(args, '--spec-oracle', oracle)
                    env['STRATA_VERIFY_ORACLE_WINDOW'] = str(width)
                else:
                    set_option(args, '--spec-oracle', None)
                log_path = d / 'engine.log'
                engine = None
                try:
                    startup = time.monotonic()
                    engine = StrataEngine(cfg['exe'], args, cfg.get('cwd', str(ROOT)), str(log_path), env)
                    startup_s = time.monotonic() - startup
                    arrivals, tokens = [], []
                    start = time.monotonic()
                    actual_limit = request_limit(path, maximum, len(expected))
                    for token in engine.generate(ids, actual_limit, {'temperature': 0}, threading.Event()):
                        if token is not None:
                            tokens.append(token)
                            arrivals.append(time.monotonic() - start)
                    wall = time.monotonic() - start
                    timings = dict(engine.last)
                finally:
                    if engine is not None:
                        engine.close()
                log = log_path.read_text()
                widths, commits = parse_histogram(log)
                observation = {'task': name, 'args': args,
                               'env': {k: v for k, v in env.items() if k.startswith('STRATA_') or k in cfg.get('env', {})},
                               'input_tokens': len(ids), 'prompt_sha256': digest(ids),
                               'requested_output_budget': maximum, 'engine_output_limit': actual_limit,
                               'token_ids': tokens, 'token_sha256': digest(tokens),
                               'output_tokens': len(tokens), 'timings': timings,
                               'startup_seconds': startup_s, 'wall_seconds': wall,
                               'decode_tps': 1000 * len(tokens) / timings['decode_ms'],
                               'effective_output_tps': 1000 * len(tokens) / (timings['prompt_ms'] + timings['decode_ms']),
                               'wall_output_tps': len(tokens) / wall, 'ttft_seconds': arrivals[0] if arrivals else None,
                               'natural_stop': timings.get('finish') == 'stop',
                               'width_histogram': widths, 'committed_histogram': commits,
                               'graph_setup_lines': [x for x in log.splitlines() if 'GRAPH_SETUP ' in x],
                               'decode_timing_lines': [x for x in log.splitlines() if x.startswith('strata decode timing:')],
                               'state_hashes': [dict(re.findall(r'(\w+)=([^\s]+)', x)) for x in log.splitlines()
                                                if 'strata serve: STATE_HASH ' in x]}
                record['results'].append(observation)
                save()
                validate_observation(job, tokens, expected, timings, widths, commits)
                if job.get('state_hash'):
                    if len(observation['state_hashes']) != 1:
                        raise ValueError('Expected exactly one target-state snapshot')
                    if int(observation['state_hashes'][0]['L']) != len(ids) + len(tokens) - 1:
                        raise ValueError('Target consumed state does not match the emitted prefix')
                observation['output_and_count_gate_passed'] = True
                save()
                print(json.dumps({'completed': label, 'decode_tps': observation['decode_tps'],
                                  'widths': widths, 'committed': commits}), flush=True)
            record['finished'] = time.time()
            save()
    except BaseException as error:
        status['error'] = repr(error)
        raise
    else:
        status['completed'] = True
    finally:
        status['finished'] = time.time()
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    opt = parser.parse_args()
    run(opt.manifest, opt.output)
