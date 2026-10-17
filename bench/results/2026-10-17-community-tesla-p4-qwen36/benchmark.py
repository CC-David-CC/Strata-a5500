"""Bounded, single-P4 release smoke and throughput test. Run in the R730 venv."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import psutil
import requests

ROOT = Path(os.environ['STRATA_CHECKOUT']).resolve()
OUT = Path(os.environ['BENCH_OUTPUT']).resolve()
MODEL = Path(os.environ['QWEN36_GGUF']).resolve()
TOKENIZER = OUT / 'data/packs/qwen36-q4/tokenizer'
PORT = 18445
URL = f'http://127.0.0.1:{PORT}'
TIMING = re.compile(r'prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms \(([\d.]+) tok/s\), (\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)')


def monitor(proc, samples, stop):
    while not stop.is_set():
        try:
            p = psutil.Process(proc.pid)
            rss = sum(x.memory_info().rss for x in [p, *p.children(recursive=True)] if x.is_running())
            gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'], text=True)
            samples.append({'time': time.time(), 'rss_bytes': rss, 'gpus': [[int(v.strip()) for v in line.split(',')] for line in gpu.strip().splitlines()]})
        except (psutil.Error, subprocess.SubprocessError):
            pass
        stop.wait(1)


def request(label, content, max_tokens, engine_log):
    offset = engine_log.stat().st_size if engine_log.exists() else 0
    start = time.monotonic()
    response = requests.post(URL + '/v1/chat/completions', json={
        'model': 'strata', 'messages': [{'role': 'user', 'content': content}],
        'temperature': 0, 'presence_penalty': 0, 'max_tokens': max_tokens, 'reasoning_effort': 'none',
        'stream': True, 'stream_options': {'include_usage': True},
    }, stream=True, timeout=(10, 300))
    response.raise_for_status()
    events, answer, ttft = [], '', None
    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
        if not line.startswith('data: '):
            continue
        payload = line[6:]
        if payload == '[DONE]':
            break
        event = json.loads(payload)
        if 'error' in event:
            raise RuntimeError(event)
        events.append(event)
        for choice in event.get('choices', []):
            delta = choice.get('delta', {})
            text = delta.get('content') or delta.get('reasoning_content') or ''
            if text and ttft is None:
                ttft = time.monotonic() - start
            answer += text
    elapsed = time.monotonic() - start
    time.sleep(0.1)
    with engine_log.open(errors='replace') as stream:
        stream.seek(offset)
        new_log = stream.read()
    matches = TIMING.findall(new_log)
    result = {'label': label, 'wall_s': elapsed, 'ttft_s': ttft, 'answer': answer, 'events': events, 'engine_log': new_log}
    if matches:
        m = matches[-1]
        result['timing'] = dict(zip(['prompt_tokens', 'reused_tokens', 'fresh_tokens', 'prompt_ms', 'prompt_tps', 'generated_tokens', 'decode_ms', 'decode_tps', 'accepted_drafts', 'proposed_drafts'], map(float, m)))
    print(json.dumps({k: v for k, v in result.items() if k not in ('events', 'engine_log', 'answer')}) , flush=True)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'tools'))
    from strata_tokenizer import Tokenizer
    tokenizer = Tokenizer.from_gguf(MODEL)
    lines = '\n'.join(f'Record {i}: service alpha has {i % 7 + 2} active workers and uses a bounded queue for tasks.' for i in range(600))
    ids = tokenizer.encode(lines)
    long_text = tokenizer.decode(ids[:3900])
    results = {'source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(), 'model': str(MODEL), 'context': 8192, 'gpu': 0, 'cpu_threads': 14, 'numa_node': 0, 'arms': []}
    for mtp in map(int, os.environ.get('BENCH_MTP', '0,2').split(',')):
        tag = f'mtp{mtp}'
        log = OUT / f'{tag}-engine.log'
        cfg = {'exe': str(Path(os.environ['STRATA_ENGINE']).resolve()), 'args': ['--native', str(MODEL), '--max-context', '8192', '--prefill', 'auto', '--mtp', str(mtp), '--pool-workers', '14'], 'cwd': str(ROOT), 'tokenizer': str(TOKENIZER), 'model_name': 'qwen3.6-35b-a3b-ud-q4_k_xl', 'arch': 'qwen35moe', 'log': str(log), 'gpu': '0', 'gpus_asked': True, 'cuda': 12, 'port': PORT, 'host': '127.0.0.1', 'open_browser': False}
        config = OUT / f'{tag}-config.json'
        samples, stop = [], threading.Event()
        cfg['env'] = {} if os.environ.get('BENCH_Q8_PACKED') == 'auto' else {'STRATA_Q8_PACKED': '0'}
        config.write_text(json.dumps(cfg, indent=2))
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='0', PYTHONUNBUFFERED='1')
        env.pop('STRATA_Q8_PACKED', None)
        env.update(cfg['env'])
        # Bind the CPU experts and model memory to GPU 0's NUMA socket.
        with (OUT / f'{tag}-server.log').open('w') as stdout:
            proc = subprocess.Popen(['numactl', '--cpunodebind=0', '--membind=0', sys.executable, str(ROOT / 'serve/server.py'), '--engine', 'strata', '--config', str(config), '--port', str(PORT)], cwd=ROOT, env=env, stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True)
            thread = threading.Thread(target=monitor, args=(proc, samples, stop), daemon=True)
            thread.start()
            arm = {'mtp': mtp, 'config': cfg, 'requests': []}
            results['arms'].append(arm)
            try:
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError(f'{tag}: server exited {proc.returncode}; see {tag}-server.log')
                    try:
                        health = requests.get(URL + '/health', timeout=2).json()
                        if health.get('loaded'):
                            arm['health'] = health
                            break
                    except (requests.RequestException, ValueError):
                        pass
                    time.sleep(2)
                else:
                    raise TimeoutError(f'{tag}: model loading exceeded 600 seconds')
                cases = [('warmup', 'Write a short paragraph explaining a queue.', 32), ('arithmetic', 'Reply with only the integer: what is 17 + 25?', 32)]
                cases += [(f'short-{i}', f'Trial {i}. Explain in detail how a bounded work queue handles backpressure and retries. Continue for at least 200 words.', 128) for i in range(3)]
                cases += [(f'long-{i}', f'Document trial {i}.\n{long_text}\nExplain the common design in these records, then discuss three ways to improve reliability. Write at least 200 words.', 128) for i in range(2)]
                for label, prompt, maximum in cases:
                    arm['requests'].append(request(label, prompt, maximum, log))
                    (OUT / 'results.json').write_text(json.dumps(results, indent=2))
                arm['arithmetic_pass'] = arm['requests'][1]['answer'].strip() == '42'
            finally:
                stop.set()
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                thread.join(timeout=3)
                (OUT / f'{tag}-resources.json').write_text(json.dumps(samples, indent=2))
                arm['peak_process_tree_rss_gib'] = max((x['rss_bytes'] / 2**30 for x in samples), default=None)
                arm['peak_gpu_mib'] = {str(i): max((gpu[1] for x in samples for gpu in x['gpus'] if gpu[0] == i), default=None) for i in range(3)}
                (OUT / 'results.json').write_text(json.dumps(results, indent=2))
        time.sleep(3)
    print('BENCHMARK COMPLETE', flush=True)
    (OUT / 'benchmark.complete').write_text('complete\n')


if __name__ == '__main__':
    main()
