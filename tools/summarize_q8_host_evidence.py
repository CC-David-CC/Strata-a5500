#!/usr/bin/env python3
"""Export measured host-path results without publishing prompt/output text."""
from pathlib import Path
import argparse
import hashlib
import json

parser = argparse.ArgumentParser()
parser.add_argument('live', type=Path, help='JSON saved by the fleet collector')
parser.add_argument('output', type=Path)
args = parser.parse_args()
live = json.loads(args.live.read_text())
wanted = {
    'rtxpro-q8-host-baseline-20261004', 'rtxpro-q8-host-candidate-20261004-r2',
    'rtxpro-q8-duplex-model-20261004', 'rtxpro-q8-worker-placement-20261004',
    'rtxpro-q8-duplex-reverse-20261004'
}
out = dict(collected_unix=live['time'],
    scope='RTX PRO 6000 Blackwell Workstation96GB,7950X,128GB RAM; full Q8_0 FP16 KV/native RoPE,15472 GPUslots,1024output,ownership rotationON; coding thenediting per freshcontext/mode engine.',
    source_evidence_sha256=hashlib.sha256(args.live.read_bytes()).hexdigest(),
    comparison_scope='Exact token streams and recorded work counters within each arm pair. Not a general internal-state proof. Ngram work/token mismatches are retained.',
    suites=[])
for job in live['jobs']:
    if job['label'] not in wanted:
        continue
    if not job.get('status', {}).get('completed'):
        raise RuntimeError('Required suite is not complete: '+job['label'])
    suite = dict(name=job['label'], records=[])
    for matrix in job['matrices'].values():
        if not matrix.get('completed'):
            continue
        for record in matrix['records']:
            row = {k: record[k] for k in ('trial', 'started', 'finished', 'exit',
                   'engine_sha256', 'prompt_sha256', 'allocated_context',
                   'comparisons', 'rotation_active', 'duplex_active', 'duplex_swaps',
                   'diagnostics') if k in record}
            row['cases'] = []
            for run in record.get('runs', []):
                for case in run['cases']:
                    c = {k: case[k] for k in ('task', 'repetition', 'input_tokens',
                         'output_tokens', 'decode_tps', 'effective_output_tps',
                         'first_token_seconds', 'timings') if k in case}
                    c['token_ids_sha256'] = hashlib.sha256(
                        json.dumps(case['token_ids'], separators=(',', ':')).encode()).hexdigest()
                    row['cases'].append(c)
            suite['records'].append(row)
    out['suites'].append(suite)
if {s['name'] for s in out['suites']} != wanted:
    raise RuntimeError('Missing required evidence')
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(out, indent=2)+'\n')
print(f"Saved {len(out['suites'])} completed suites to {args.output}")
