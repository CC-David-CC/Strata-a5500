"""HTTP client, exact-request native receipts, and request-local trace events."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = ROOT / 'docs/control-lab-evidence/recordings'


def request_key(body):
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def base_request(prompt, *, max_tokens=16, top=20):
    return dict(model='x', messages=[dict(role='user', content=prompt)], temperature=0,
                reasoning_effort='none', seed=675, max_tokens=max_tokens,
                logprobs=True, top_logprobs=top)


def collect_chunks(chunks):
    message = {'role': 'assistant', 'content': ''}
    scores, tool_calls, usage, timings, finish = [], {}, {}, {}, None
    for chunk in chunks:
        if 'error' in chunk:
            raise ValueError(f"Strata stream failed: {chunk['error']}")
        usage = chunk.get('usage') or usage
        timings = chunk.get('timings') or timings
        for choice in chunk.get('choices', []):
            delta = choice.get('delta') or {}
            for key in ('content', 'reasoning_content'):
                if delta.get(key):
                    message[key] = message.get(key, '') + delta[key]
            for call in delta.get('tool_calls') or []:
                item = tool_calls.setdefault(call['index'], {'type': 'function', 'function': {'name': '', 'arguments': ''}})
                if call.get('id'):
                    item['id'] = call['id']
                fn = call.get('function') or {}
                for key in ('name', 'arguments'):
                    item['function'][key] += fn.get(key) or ''
            scores.extend((choice.get('logprobs') or {}).get('content') or [])
            finish = choice.get('finish_reason') or finish
    if finish is None:
        raise ValueError("Stream ended without a terminal choice")
    if tool_calls:
        message['tool_calls'] = [tool_calls[i] for i in sorted(tool_calls)]
    return {'choices': [{'message': message, 'logprobs': {'content': scores}, 'finish_reason': finish}],
            'usage': usage, 'timings': timings}


class Backend:
    def __init__(self, mode, *, base_url=None, api_key=None, recordings=RECORDINGS,
                 capture=None, transport=None):
        self.mode = mode
        self.base_url = (base_url or os.environ.get('STRATA_BASE_URL', 'http://127.0.0.1:8080')).rstrip('/')
        self.api_key = api_key if api_key is not None else os.environ.get('STRATA_API_KEY', '')
        self.recordings = Path(recordings)
        self.capture = Path(capture) if capture else None
        self.transport = transport
        self.cursors = {}
        self.http = None

    async def __aenter__(self):
        headers = {'Authorization': 'Bearer ' + self.api_key} if self.api_key else {}
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10), headers=headers,
                                      transport=self.transport, follow_redirects=False, trust_env=False)
        return self

    async def __aexit__(self, *exc):
        await self.http.aclose()

    async def call(self, body, emit):
        key = request_key(body)
        if self.mode == 'recorded':
            paths = sorted(self.recordings.glob(key + '-*.json'))
            if not paths:
                raise ValueError("No native recording matches these inputs. Restore this page's example or select Live model.")
            index = self.cursors.get(key, 0)
            if index >= len(paths):
                raise ValueError("This recording has no further repetitions. Switch to Live model to measure more.")
            self.cursors[key] = index + 1
            record = json.loads(paths[index].read_text(encoding='utf-8'))
            if record['request'] != body or record.get('provenance') != 'native-strata':
                raise ValueError("Recording identity/provenance check failed")
            await asyncio.sleep(0)
            for chunk in record.get('chunks', []):
                await emit('token', {'chunk': chunk, 'recorded': True})
            return record
        started, chunks = time.perf_counter(), []
        url = self.base_url + '/v1/chat/completions'
        if body.get('stream'):
            async with self.http.stream('POST', url, json=body) as response:
                if response.status_code != 200:
                    raw = await response.aread()
                    raise ValueError(f"Strata HTTP {response.status_code}: {raw.decode('utf-8', errors='replace')[:1200]}")
                event_lines, done = [], False
                async for line in response.aiter_lines():
                    if line.startswith('data:'):
                        event_lines.append(line[5:].lstrip())
                    elif not line and event_lines:
                        data = '\n'.join(event_lines)
                        event_lines = []
                        if data == '[DONE]':
                            done = True
                            break
                        chunk = json.loads(data)
                        if 'error' in chunk:
                            raise ValueError(f"Strata stream failed: {chunk['error']}")
                        chunks.append(chunk)
                        await emit('token', {'chunk': chunk, 'recorded': False})
                if not done:
                    raise ValueError("Strata closed its stream before [DONE]")
            reply = collect_chunks(chunks)
        else:
            response = await self.http.post(url, json=body)
            if response.status_code != 200:
                raise ValueError(f"Strata HTTP {response.status_code}: {response.text[:1200]}")
            reply = response.json()
            if 'error' in reply:
                raise ValueError(f"Strata failed: {reply['error']}")
        record = dict(provenance='native-strata', request=body, response=reply, chunks=chunks,
                      wall_ms=(time.perf_counter() - started) * 1000,
                      captured_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        if self.capture:
            self.capture.mkdir(parents=True, exist_ok=True)
            index = len(list(self.capture.glob(key + '-*.json')))
            path = self.capture / f'{key}-{index:03}.json'
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        return record


class Context:
    def __init__(self, backend, emit):
        self.backend, self.emit = backend, emit
        self.calls = []
        self.sequence = 0

    async def call(self, title, body):
        self.sequence += 1
        step = self.sequence
        await self.emit('step', {'id': step, 'title': title, 'status': 'running', 'request': body})
        record = await self.backend.call(body, self.emit)
        self.calls.append(record)
        await self.emit('step', {'id': step, 'title': title, 'status': 'completed',
                                 'wall_ms': record['wall_ms'], 'response': record['response']})
        return record['response']

    def receipt(self):
        return {'mode': self.backend.mode, 'requests': len(self.calls),
                'summed_request_ms': math.fsum(c['wall_ms'] for c in self.calls),
                'prompt_tokens': sum(c['response'].get('usage', {}).get('prompt_tokens', 0) for c in self.calls),
                'completion_tokens': sum(c['response'].get('usage', {}).get('completion_tokens', 0) for c in self.calls),
                'calls': self.calls}
