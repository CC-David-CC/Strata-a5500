"""Replay the published 32-request plan with local model/configuration paths."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = {
    'serial': 'pw=0 theta=0.2 force_miss=0 short_read=0',
    'pipeline': 'pw=2 theta=0.2 force_miss=0 short_read=0',
    'rollback': 'pw=2 theta=0 force_miss=1 short_read=0',
    'no_guess': 'pw=2 theta=2 force_miss=0 short_read=0',
}


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    options = parser.parse_args()
    cfg = json.loads(options.config.read_text(encoding='utf-8'))
    if '/path/to/' in json.dumps(cfg):
        parser.error('Replace /path/to/ placeholders in your local configuration.')
    out = options.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(cfg['cwd'])
    sys.path[:0] = [str(root), str(root / 'tools')]
    from serve.server import StrataEngine, child_env, engine_args
    from strata_tokenizer import Tokenizer

    published = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
    prompts, plan = published['prompts'], published['plan']
    expected = {r['prompt']: r['tokens'] for r in published['runs'] if r['mode'] == 'serial'}
    args = engine_args(cfg)
    tok = Tokenizer.from_gguf(Path(args[args.index('--native') + 1]))
    switch = out / 'switch.txt'
    env = child_env(cfg)
    env.update(STRATA_PIPELINE_DEBUG='1', STRATA_PIPELINE_SWITCH=str(switch), STRATA_DECODE_TIMING='1')
    report = dict(
        config=cfg, args=args, plan=plan, prompts=prompts,
        commit=subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
        diff_sha256=hashlib.sha256(subprocess.check_output(['git', '-C', str(root), 'diff', 'HEAD', '--binary'])).hexdigest(),
        exe_sha256=hashlib.sha256(Path(cfg['exe']).read_bytes()).hexdigest(),
        runs=[], complete=False,
    )
    engine, refs = None, {}
    log = out / 'engine.log'
    try:
        save(out / 'result.json', report)
        start = time.monotonic()
        engine = StrataEngine(cfg['exe'], args, cfg['cwd'], str(log), env)
        report.update(startup_s=time.monotonic() - start, engine_info=engine.info)
        for entry in plan:
            key, mode = entry['prompt'], entry['mode']
            switch.write_text(MODES[mode], encoding='utf-8')
            offset = log.stat().st_size
            print('START', json.dumps(entry), flush=True)
            start, tokens, first = time.monotonic(), [], None
            timer = threading.Timer(1200, engine.proc.kill)
            timer.start()
            try:
                for token in engine.generate(prompts[key], entry.get('output', 256), {'temperature': 0}, threading.Event()):
                    if token is not None:
                        tokens.append(token)
                        if first is None:
                            first = time.monotonic() - start
            finally:
                timer.cancel()
            timing = dict(engine.last)
            section = log.read_bytes()[offset:].decode(errors='replace')
            row = dict(
                entry, tokens=tokens, text=tok.decode(tokens), timing=timing,
                wall_s=time.monotonic() - start, ttft_s=first,
                decode_tps=len(tokens) * 1000 / timing['decode_ms'],
                prefill_tps=len(prompts[key]) * 1000 / timing['prompt_ms'],
                kept=sum(map(int, re.findall(r'(\d+) on the path', section))),
                rolled_back=sum(map(int, re.findall(r'(\d+) rolled back', section))),
            )
            if key not in refs:
                assert mode == 'serial'
                refs[key] = tokens
            row['matches_serial'] = tokens == refs[key]
            row['matches_published_serial'] = tokens == expected[key]
            report['runs'].append(row)
            save(out / 'result.json', report)
            print('RESULT', json.dumps({k: v for k, v in row.items() if k not in ['tokens', 'text']}), flush=True)
            assert tokens and timing.get('reused', 0) == 0
        report['complete'] = True
        report['all_match_serial'] = all(r['matches_serial'] for r in report['runs'])
    except BaseException:
        report['error'] = traceback.format_exc()
        raise
    finally:
        if engine:
            engine.close()
        save(out / 'result.json', report)
    if not report['all_match_serial'] or not all(r['matches_published_serial'] for r in report['runs']):
        raise SystemExit('Token equality failed; inspect result.json before interpreting throughput.')


if __name__ == '__main__':
    main()
