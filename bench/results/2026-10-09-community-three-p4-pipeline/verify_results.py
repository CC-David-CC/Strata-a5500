"""Audit the saved report data without starting a GPU process."""
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent


def main():
    report = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
    summary = json.loads((HERE / 'summary.json').read_text(encoding='utf-8'))
    diagnostic = json.loads((HERE / 'correctness.json').read_text(encoding='utf-8'))
    refs = {}
    assert report['complete'] and report['all_match_serial']
    assert len(report['runs']) == len(report['plan']) == 32
    assert Counter(r['phase'] for r in report['runs']) == {'warmup': 2, 'performance': 24, 'control': 6}
    for entry, row in zip(report['plan'], report['runs']):
        assert all(row[key] == value for key, value in entry.items())
        prompt, mode, tokens, timing = row['prompt'], row['mode'], row['tokens'], row['timing']
        assert len(report['prompts'][prompt]) == int(prompt.split(':')[0]) == timing['prompt_tokens']
        assert timing['reused'] == 0 and timing['prompt_read'] == timing['prompt_tokens']
        assert len(tokens) == timing['generated'] == (125 if prompt.endswith(':code') else 256)
        if prompt not in refs:
            assert mode == 'serial'
            refs[prompt] = tokens
        assert row['matches_serial'] and tokens == refs[prompt]
        if prompt in diagnostic['original_serial_tokens']:
            assert row['matches_original_serial'] and tokens == diagnostic['original_serial_tokens'][prompt]
        assert math.isclose(row['decode_tps'], len(tokens) * 1000 / timing['decode_ms'], rel_tol=1e-12)
        assert math.isclose(row['prefill_tps'], timing['prompt_read'] * 1000 / timing['prompt_ms'], rel_tol=1e-12)
    for item in summary:
        rows = [r for r in report['runs'] if r['phase'] == 'performance' and r['prompt'] == item['prompt'] and r['mode'] == item['mode']]
        assert len(rows) == item['repetitions'] == 3
        for metric in ['decode_tps', 'prefill_tps', 'ttft_s', 'wall_s']:
            vals = [r[metric] for r in rows]
            assert item[metric] == dict(median=median(vals), min=min(vals), max=max(vals), values=vals)
    rollback = [r['rolled_back'] for r in report['runs'] if r['mode'] == 'rollback']
    assert rollback == [62, 157, 128]
    log = (HERE / 'engine.log').read_text(encoding='utf-8')
    timing_lines = re.findall(r'strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms .*?, (\d+) generated in (\d+) ms', log)
    assert len(timing_lines) == 32
    for values, row in zip(timing_lines, report['runs']):
        prompt, reused, fresh, prompt_ms, generated, decode_ms = map(int, values)
        timing = row['timing']
        assert (prompt, reused, fresh, generated) == (timing['prompt_tokens'], 0, timing['prompt_read'], timing['generated'])
        assert abs(prompt_ms - timing['prompt_ms']) <= 0.51
        assert abs(decode_ms - timing['decode_ms']) <= 0.51
    print('Verified 32 token-equal requests, 24 measured runs, all medians/ranges, and 32 engine timing lines.')


if __name__ == '__main__':
    main()
