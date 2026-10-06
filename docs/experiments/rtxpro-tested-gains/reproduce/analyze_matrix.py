"""Summarize completed ordinary requests; preserve mismatches and every metric."""
from pathlib import Path
import argparse
import hashlib
import json

parser = argparse.ArgumentParser()
parser.add_argument('matrix', type=Path)
args = parser.parse_args()
root = args.matrix
plan = json.loads((root / 'plan.json').read_text())
results = {}
for case in plan['cases']:
    path = root / case['label'] / 'result.json'
    if not path.exists():
        continue
    result = json.loads(path.read_text())
    if not result.get('completed'):
        continue
    bench = result['benchmark']
    assert result['function_check']['passed'], case['label']
    assert bench['output_tokens'] == case['output_tokens'], case['label']
    assert bench['timings']['prompt_read'] == case['input_tokens'], case['label']
    assert bench['timings'].get('reused', 0) == 0, case['label']
    results[case['label']] = result

rows, pairs = [], []
for case in plan['cases']:
    label = case['label']
    if label not in results:
        continue
    result = results[label]
    bench = result['benchmark']
    rows.append(dict(label=label, model=case['model'], arm=case['build'],
        input_tokens=case['input_tokens'], output_tokens=bench['output_tokens'],
        path='combined' if case['ngram'] and case['mtp_t'] > 1 else
             'ngram' if case['ngram'] else 'mtp' if case['mtp_t'] > 1 else 'plain',
        prefill_s=bench['timings']['prompt_ms'] / 1000,
        decode_tps=bench['decode_tok_s'], effective_tps=bench['effective_tok_s'],
        total_s=bench['wall_seconds'], model_cpu_s=bench['model_cpu_seconds'],
        engine_sha256=result['engine_sha256'],
        input_sha256=result['input_token_ids_sha256'],
        output_sha256=hashlib.sha256(json.dumps(bench['token_ids']).encode()).hexdigest(),
        activation_checks=result.get('activation_checks', []),
        reused_stock_observation=bool(case.get('reuse_verified_baseline_from'))))
    if case['build'] != 'stock':
        continue
    other = label.removesuffix('-stock') + '-combined'
    if other not in results:
        continue
    a, b = result, results[other]
    assert a['input_token_ids_sha256'] == b['input_token_ids_sha256'], label
    x, y = a['benchmark'], b['benchmark']
    difference = next((i for i, (u, v) in enumerate(zip(x['token_ids'], y['token_ids']))
                       if u != v), None)
    ignored = {'prompt_ms', 'decode_ms'}
    work_a = {k: v for k, v in x['timings'].items() if k not in ignored}
    work_b = {k: v for k, v in y['timings'].items() if k not in ignored}
    changes = {k: [work_a.get(k), work_b.get(k)] for k in work_a.keys() | work_b.keys()
               if work_a.get(k) != work_b.get(k)}
    pairs.append(dict(labels=[label, other], model=case['model'],
        input_tokens=case['input_tokens'], first_difference_zero_based=difference,
        exact_token_stream=difference is None, work_counter_changes=changes,
        decode_change_pct=100 * (y['decode_tok_s'] / x['decode_tok_s'] - 1),
        request_time_reduction_pct=100 * (1 - y['wall_seconds'] / x['wall_seconds']),
        cpu_time_reduction_pct=100 * (1 - y['model_cpu_seconds'] / x['model_cpu_seconds']),
        interpretation='Initial observation; changed output/work is not a controlled kernel speedup.'
                       if difference is not None or changes else
                       'Initial identical-output/work pair; no confidence interval.'))

summary = dict(scope=plan['scope'], source_branch='perf/q8-tested-gains',
               completed_cases=len(rows), planned_cases=len(plan['cases']),
               rows=rows, pairs=pairs,
               limitations=['Single observation per arm.',
                   'Ordinary timings, no profiler attached.',
                   'Short pure-arithmetic function check; long generated module not executed or scored.',
                   'CPU time from Linux proc ticks, aggregate across engine threads; not system-wide energy.',
                   'No peak RAM/VRAM sampling in these ordinary timings.',
                   'Component/resource wins reported separately; percentages are not added.'])
(root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'completed_cases': len(rows), 'completed_pairs': len(pairs)}))
