"""Compare identical Responses continuations through live, RAM, disk and replay.

Linux/NVIDIA measurement harness. Runs loopback servers, never production services.
Requires an MTP runtime: main's MTP-off session serialization is not used here.
Each output directory must be new. No percentiles are inferred from a single run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request

CORE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(CORE), str(CORE / 'tools')]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', required=True, type=Path)
    ap.add_argument('--exe', required=True, type=Path)
    ap.add_argument('--mtp', required=True)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--tokens', required=True, type=int)
    ap.add_argument('--port', type=int, default=18229)
    ap.add_argument('--modes', nargs='+', choices=['live', 'ram', 'disk'], default=['live', 'ram', 'disk'])
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    source = json.loads(a.config.read_text())
    import strata_tokenizer as ST
    from serve.frontend import ChatTemplate
    from serve.responses import template_kwargs
    tp = Path(source['tokenizer'])
    vocab = json.loads((tp / 'vocab.json').read_text())
    tokens = [None] * len(vocab)
    for text, index in vocab.items():
        tokens[index] = text
    tok = ST.Tokenizer(tokens, (tp / 'merges.txt').read_text().split('\n'), json.loads((tp / 'token_type.json').read_text()))
    template = ChatTemplate(tp / 'chat_template.jinja')
    kw = template_kwargs({'reasoning': {'effort': 'none'}}, {})
    kw['preserve_empty_reasoning'] = True
    expected = ['CEDAR-731', 'MARBLE-482', 'QUARTZ-956']

    def prompt(n):
        text = ('Start verification code: CEDAR-731.\n' + ' apple' * (n // 2) +
                '\nMiddle verification code: MARBLE-482.\n' + ' orange' * (n - n // 2) +
                '\nEnd verification code: QUARTZ-956.\nReply with READY only.')
        ids = tok.encode(template.render([{'role': 'user', 'content': text}], tools=None, **kw), parse_special=True)
        return text, ids
    lo, hi = 0, a.tokens
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(prompt(mid)[1]) <= a.tokens:
            lo = mid
        else:
            hi = mid - 1
    text, ids = prompt(lo)
    assert len(ids) == a.tokens
    follow = 'Return all three verification codes from the document in order, separated by |. Nothing else.'
    rows, audits, samples = [], [], []
    result = dict(prefix_tokens=a.tokens, prefix_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
                  exe_sha256=hashlib.sha256(a.exe.read_bytes()).hexdigest(), rows=rows, audits=audits,
                  samples_per_condition=1, output_cap=128, kv='fp16', mtp_spec=4,
                  rope='ordinary' if a.tokens <= 262144 else 'yarn',
                  rope_factor=1 if a.tokens <= 262144 else a.tokens // 262144)
    def save():
        temp = a.output / 'results.tmp'
        temp.write_text(json.dumps(result, indent=2))
        temp.replace(a.output / 'results.json')
    save()

    def call(path, body=None):
        req = urllib.request.Request(f'http://127.0.0.1:{a.port}' + path,
            data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=14400) as response:
            return json.load(response)

    def sql(path, statement, args=()):
        with sqlite3.connect(path) as db:
            return db.execute(statement, args).fetchall()

    for mode in a.modes:
        root = a.output / mode
        root.mkdir()
        state = root / 'state'
        raw, args, i = source['args'], [], 0
        replace = {'--max-context', '--kv', '--kv-resident', '--mtp', '--spec', '--conversation-cache-mib',
                   '--conversation-cache-spill-dir', '--conversation-cache-disk-mib', '--rope-scaling',
                   '--rope-scale', '--rope-freq-scale', '--yarn-orig-ctx', '--prefill', '--suffix-draft'}
        while i < len(raw):
            if raw[i] in replace:
                i += 2
            elif raw[i] == '--conversation-cache-disk-only':
                i += 1
            else:
                args.append(raw[i]); i += 1
        args += ['--max-context', str(a.tokens + 4096), '--kv', 'fp16', '--spec', '4', '--mtp', a.mtp,
                 '--suffix-draft', '0', '--prefill', '8192', '--conversation-cache-mib', '40960' if mode == 'ram' else '0',
                 '--rope-scaling', 'none' if a.tokens <= 262144 else 'yarn']
        if a.tokens > 262144:
            args += ['--rope-scale', str(a.tokens // 262144), '--yarn-orig-ctx', '262144']
        # Build a plain Strata configuration; do not inherit private profile settings.
        cfg = {k: source[k] for k in ['tokenizer', 'gpu', 'lib_dirs'] if k in source}
        cfg.update(exe=str(a.exe), cwd=str(CORE), args=args, env={'STRATA_PREFILL_CPU_SHARE': '0'},
                   host='127.0.0.1', port=a.port, api_key='', state=str(state),
                   experimental_branch_checkpoints=True, responses_store_path=str(state / 'responses'),
                   checkpoint_budget_mib=102400 if mode == 'disk' else 0,
                   checkpoint_max_snapshot_mib=1024 + a.tokens // 32,
                   history_reserve_mib=4096, log=str(root / 'engine.log'))
        config = root / 'config.json'
        config.write_text(json.dumps(cfg, indent=2))
        catalog = state / 'responses/execution-cache/checkpoints.sqlite3'
        history = state / 'responses/responses.sqlite3'
        process = None
        phase = 'startup'
        done = threading.Event()
        def monitor():
            while not done.is_set():
                row = dict(mode=mode, phase=phase, time=time.time())
                try:
                    pids = [process.pid] if process and process.poll() is None else []
                    if pids:
                        children = Path(f'/proc/{pids[0]}/task/{pids[0]}/children').read_text().split()
                        pids += [int(p) for p in children]
                    rss = swap = 0
                    for pid in pids:
                        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                            if line.startswith('VmRSS:'): rss += int(line.split()[1])
                            if line.startswith('VmSwap:'): swap += int(line.split()[1])
                    row.update(rss_kib=rss, swap_kib=swap)
                    row['gpu_mib'] = int(subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True, timeout=3).strip())
                    row['disk_free_bytes'] = os.statvfs(root).f_bavail * os.statvfs(root).f_frsize
                except Exception as exc:
                    row['error'] = repr(exc)
                samples.append(row)
                done.wait(1)
        worker = threading.Thread(target=monitor, daemon=True)
        worker.start()
        log = (root / 'server.log').open('a')
        def start():
            nonlocal process, phase
            phase = 'startup'
            began = time.perf_counter()
            env = dict(os.environ, PYTHONUNBUFFERED='1')
            env.pop('STRATA_API_KEY', None)
            process = subprocess.Popen([sys.executable, '-m', 'serve.server', '--engine', 'strata', '--config', str(config), '--port', str(a.port)],
                cwd=CORE, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            for _ in range(1800):
                if process.poll() is not None: raise RuntimeError('server exited: ' + str(root))
                try:
                    call('/v1/models')
                    audits.append(dict(mode=mode, startup_s=time.perf_counter()-began)); save(); return
                except OSError: time.sleep(1)
            raise TimeoutError('server startup')
        def stop():
            if process and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try: process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()
                    raise RuntimeError('graceful stop timed out')

        def generate(label, input_text, previous=None):
            nonlocal phase
            phase = label
            before = dict(sql(catalog, 'SELECT id,last_used FROM successful_restores'))
            log_start = (root / 'engine.log').stat().st_size
            body = dict(input=input_text, max_output_tokens=128, reasoning={'effort': 'none'}, temperature=0, stream=True)
            if previous: body['previous_response_id'] = previous
            req = urllib.request.Request(f'http://127.0.0.1:{a.port}/v1/responses', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            began = time.perf_counter(); first = last = final = None; answer = ''
            with urllib.request.urlopen(req, timeout=14400) as response:
                for line in response:
                    if not line.startswith(b'data: '): continue
                    event = json.loads(line[6:])
                    if event['type'] == 'response.output_text.delta':
                        last = time.perf_counter(); first = first or last; answer += event['delta']
                    if event['type'] in ('response.completed', 'response.incomplete', 'response.failed'):
                        final = event['response']
            elapsed = time.perf_counter() - began
            after = dict(sql(catalog, 'SELECT id,last_used FROM successful_restores'))
            with (root / 'engine.log').open('rb') as f:
                f.seek(log_start); native = f.read().decode(errors='replace')
            (root / (label + '-native.log')).write_text(native)
            row = dict(mode=mode, label=label, ttft_s=None if first is None else first-began,
                       last_text_s=None if last is None else last-began, total_s=elapsed, answer=answer, response=final,
                       disk_restores=sum(before.get(k) != v for k, v in after.items()),
                       ram_restore='conversation cache: restored' in native,
                       checkpoint_bytes=sum(p.stat().st_size for p in (catalog.parent / 'blocks').glob('*') if p.is_file()))
            if final:
                record = sql(history, 'SELECT prompt FROM execution_records WHERE response_id=?', (final['id'],))
                if record:
                    prompt_ids = json.loads(record[0][0])
                    row.update(input_tokens=len(prompt_ids), input_sha256=hashlib.sha256(json.dumps(prompt_ids).encode()).hexdigest())
                row['cached_tokens'] = final.get('usage', {}).get('input_tokens_details', {}).get('cached_tokens', 0)
            if previous: row['correct_codes'] = [code in answer for code in expected]
            rows.append(row); save()
            print(mode, label, json.dumps({k: v for k, v in row.items() if k != 'response'}), flush=True)
            assert final and final['status'] == 'completed', row
            return final['id'], row
        try:
            start()
            base, seeded = generate('seed-prefill', text)
            assert seeded['input_tokens'] == a.tokens
            if mode == 'live':
                _, reused = generate('live-reuse', follow, base)
                generate('distraction', 'Reply with READY only.')
                _, fresh = generate('fresh-replay', follow, base)
                assert fresh['cached_tokens'] < 100
                assert fresh['input_sha256'] == reused['input_sha256']
            elif mode == 'ram':
                generate('distraction', 'Reply with READY only.')
                _, reused = generate('ram-restore', follow, base)
                assert reused['ram_restore'] and reused['disk_restores'] == 0
            else:
                assert seeded['checkpoint_bytes'] > 0, 'checkpoint admission failed'
                call('/v1/responses/' + base + '/bookmark', {'protected': True})
                stop(); start()
                _, reused = generate('disk-restore-after-restart', follow, base)
                assert reused['disk_restores'] > 0
            assert reused['cached_tokens'] > a.tokens - 1024, reused
            # Quality is recorded, not used to suppress valid timing observations.
            audits.append(dict(mode=mode, reuse_verified=True)); save()
        except Exception as exc:
            audits.append(dict(mode=mode, error=repr(exc))); save()
            raise
        finally:
            try: stop()
            finally:
                done.set(); worker.join(timeout=5); log.close()
                (a.output / 'memory-samples.json').write_text(json.dumps(samples))
                result['peak_rss_gib'] = max((s.get('rss_kib', 0) for s in samples), default=0)/1024**2
                result['peak_gpu_gib'] = max((s.get('gpu_mib', 0) for s in samples), default=0)/1024
                save()
    (a.output / 'COMPLETE').write_text('All requested tier assertions passed.\n')


if __name__ == '__main__':
    main()
