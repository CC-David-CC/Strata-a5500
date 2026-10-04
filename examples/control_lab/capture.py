"""Capture public built-in examples from a real Strata server; never fabricates responses.

python -m examples.control_lab.capture --base-url http://127.0.0.1:8080
"""
import argparse
import asyncio
import json
from pathlib import Path
import time
import sys

from .catalog import PAGES
from .client import Backend, Context, RECORDINGS, ROOT
from .scenarios import run_page


async def capture(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    async def emit(kind, data):
        if kind == 'step' and data['status'] == 'completed':
            print(f"  {data['title']}: {data['wall_ms']:.0f} ms", flush=True)
    cases = [(p['id'], {}) for p in PAGES if p['id'] != 'speculation']
    cases += [('controller', {'controller_state': state}) for state in ['inspected', 'edited', 'verified']]
    cases += [('wire', {'case': p.stem}) for p in sorted((ROOT / 'examples/logprobs').glob('*.json')) if p.stem != 'stream']
    cases += [(name, {'strategy': 'fast'}) for name in ['choice', 'boolean', 'score']]
    if args.page:
        cases = [(p, opt) for p, opt in cases if p in args.page]
    report = output / 'capture-results.json'
    results = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    for name, opt in cases:
        print(name, opt, flush=True)
        async with Backend('live', base_url=args.base_url, capture=output / 'recordings') as backend:
            ctx = Context(backend, emit)
            started = time.perf_counter()
            result = await run_page(ctx, name, opt)
            summary = dict(page=name, options=opt, result=result, receipt=ctx.receipt(),
                           wall_ms=(time.perf_counter() - started) * 1000)
            key = name + ('-' + next(iter(opt.values())) if opt else '')
            (output / (key + '.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            results = [r for r in results if not (r['page'] == name and r['options'] == opt)]
            results.append(dict(page=name, options=opt, requests=len(ctx.calls), wall_ms=summary['wall_ms']))
            (output / 'capture-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2), flush=True)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', default=str(RECORDINGS.parent))
    parser.add_argument('--page', action='append', choices=[p['id'] for p in PAGES])
    asyncio.run(capture(parser.parse_args()))


if __name__ == '__main__':
    main()
