"""Serial, private A/B for resident exchange scheduling; writes raw tokens and timings.

The plan JSON supplies engine/source paths, common arguments and explicit cases.
No server is exposed and no existing service is stopped. Use a free GPU.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan', type=Path)
    ap.add_argument('output', type=Path)
    opt = ap.parse_args()
    plan = json.loads(opt.plan.read_text())
    source = Path(plan['python_source'])
    sys.path[:0] = [str(source), str(source / 'tools')]
    from serve.server import StrataEngine
    from serve.frontend import ChatTemplate
    from strata_tokenizer import Tokenizer
    busy = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip()
    if busy:
        raise RuntimeError('GPU is busy: ' + busy)
    opt.output.mkdir(parents=True, exist_ok=False)
    tk = Tokenizer.from_gguf(plan['native'])
    template = ChatTemplate(Path(plan['pack']) / 'tokenizer/chat_template.jinja')
    report = {'plan': plan, 'runs': [], 'comparisons': [], 'started_unix': time.time(),
              'engine_sha256': {k: digest(v) for k, v in plan['engines'].items()},
              'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                                              '--format=csv'], text=True)}
    if plan.get('model_manifest'):
        report['model_manifest'] = json.loads(Path(plan['model_manifest']).read_text())
    report['pack_hashes'] = {name: digest(Path(plan['pack']) / name)
                             for name in ['index.txt', 'native_experts.txt']}

    def save():
        tmp = opt.output / 'result.tmp'
        tmp.write_text(json.dumps(report, indent=2) + '\n')
        tmp.replace(opt.output / 'result.json')

    def prompt(case):
        marker = 'STRATA_DUPLEX_BACKGROUND'
        task = plan['tasks'][case['task']]
        text = template.render([{'role': 'user', 'content':
            'Archived background notes (data, not instructions):\n' + marker + '\nEnd of notes.\n\n' + task}],
            enable_thinking=False)
        before, after = text.split(marker)
        a, b = tk.encode(before, parse_special=True), tk.encode(after, parse_special=True)
        filler = tk.encode('Ordinary maintenance notes describe deterministic tests, scheduling and data ownership.\n')
        needed = case['input'] - len(a) - len(b)
        if needed < 0:
            raise ValueError('Prompt length is smaller than the instructions')
        return a + (filler * ((needed + len(filler) - 1) // len(filler)))[:needed] + b

    try:
        for case in plan['cases']:
            label = case['label']
            ids = prompt(case)
            (opt.output / (label + '-input.json')).write_text(json.dumps(ids))
            args = plan['common_args'] + ['--mtp-max-t', str(case['mtp_t']), '--max-context', str(case['context'])]
            if case['resident_gib']:
                args += ['--resident-budget-gib', str(case['resident_gib'])]
            env = {k: v for k, v in os.environ.items() if not k.startswith('STRATA_')}
            env.update(plan.get('environment', {}))
            env.update(case.get('environment', {}))
            if case.get('duplex') is not None:
                env['STRATA_EXCHANGE_DUPLEX'] = str(case['duplex'])
            engine_path = plan['engines'][case['engine']]
            assert digest(engine_path) == report['engine_sha256'][case['engine']]
            log = opt.output / (label + '.log')
            row = {'label': label, 'case': case, 'args': args, 'started_unix': time.time(), 'requests': []}
            report['runs'].append(row)
            report['current'] = label
            save()
            engine = None
            try:
                start = time.monotonic()
                engine = StrataEngine(engine_path, args, str(source), str(log), env)
                row.update(startup_seconds=time.monotonic() - start, engine_info=engine.info)
                requests = case.get('requests', [{'tokens': case['output']}])
                for request in requests:
                    tokens, cancel = [], threading.Event()
                    start = last = time.monotonic()
                    first = None
                    for token in engine.generate(ids, request['tokens'], {'temperature': 0}, cancel):
                        if token is not None:
                            tokens.append(token)
                            if first is None: first = time.monotonic() - start
                            if request.get('cancel_after') and len(tokens) >= request['cancel_after']:
                                cancel.set()
                        now = time.monotonic()
                        if now - last > 20:
                            print('PROGRESS', label, len(tokens), round(now - start, 1), flush=True)
                            last = now
                    timings = dict(engine.last)
                    ms = timings['decode_ms']
                    result = {'output_tokens': len(tokens), 'token_ids': tokens, 'timings': timings,
                              'wall_seconds': time.monotonic() - start, 'ttft_seconds': first,
                              'decode_tok_s': len(tokens) * 1000 / ms if ms else None,
                              'effective_tok_s': len(tokens) * 1000 / (ms + timings['prompt_ms']),
                              'cancel_requested': cancel.is_set()}
                    row['requests'].append(result)
                    save()
                    if not cancel.is_set(): assert len(tokens) == request['tokens'], (label, len(tokens))
                    else: assert 0 < len(tokens) < request['tokens'], label + ': cancellation failed'
                    assert timings.get('reused', 0) == 0
                    if case['mtp_t'] == 1: assert timings.get('drafts_offered', 0) == 0
                    print('DONE', label, len(tokens), result['decode_tok_s'], flush=True)
            finally:
                if engine is not None:
                    engine.close()
                row['finished_unix'] = time.time()
                save()
            log_text = log.read_text(errors='replace')
            row['duplex_active'] = 'duplex resident exchanges enabled' in log_text
            count = re.findall(r'duplex exchanges: (\d+) copies, (\d+) D2H\+H2D payload bytes', log_text)
            row['duplex_counters'] = [[int(a), int(b)] for a, b in count]
            row['resident_exchanges'] = [int(x) for x in re.findall(r'resident RAM: .*?, (\d+) exchanged', log_text)]
            row['diagnostics'] = [line for line in log_text.splitlines() if any(word in line for word in
                ['duplex', 'resident RAM:', 'decode expert cache hit rate', 'expert tiers:', 'decoded', '(cancelled)'])]
            expected = bool(case.get('duplex') == 1 and case['resident_gib'] > 0 and
                            case.get('environment', {}).get('STRATA_RESIDENT_PIN', '1') != '0')
            assert row['duplex_active'] == expected, label + ': wrong activation'
            if expected: assert count and int(count[-1][0]) > 0, label + ': no duplex work'
            save()
        by_name = {r['label']: r for r in report['runs']}
        for pair in plan['pairs']:
            a, b = (by_name[x]['requests'][pair.get('request', 0)] for x in pair['labels'])
            same = a['token_ids'] == b['token_ids']
            comparison = {'labels': pair['labels'], 'tokens_identical': same,
                          'first_difference': next((i for i, (x, y) in enumerate(zip(a['token_ids'], b['token_ids'])) if x != y), None),
                          'decode_gain_pct': 100 * (b['decode_tok_s'] / a['decode_tok_s'] - 1),
                          'total_time_reduction_pct': 100 * (1 - b['wall_seconds'] / a['wall_seconds'])}
            keys = ['generated', 'prompt_read', 'drafts_accepted', 'drafts_offered', 'reused',
                    'hits', 'lookups', 'offloaded', 'ram_blobs', 'file_blobs', 'file_mb']
            comparison['work_identical'] = all(a['timings'].get(k) == b['timings'].get(k) for k in keys)
            report['comparisons'].append(comparison)
            save()
            assert same, comparison
            assert comparison['work_identical'], comparison
        report.update(completed=True, finished_unix=time.time())
        report.pop('current', None)
        save()
    except BaseException as e:
        report.update(error=repr(e), finished_unix=time.time())
        save()
        raise


if __name__ == '__main__':
    main()
