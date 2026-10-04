"""Replay native evidence through the UI boundary; synthetic errors are labeled."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from .app import create_app
from .catalog import PAGES
from .client import Backend, Context, collect_chunks
from .scenarios import run_page

HEADERS = {'X-Control-Lab': '1'}


@pytest.fixture
def client():
    with TestClient(create_app(), base_url='http://localhost') as client:
        yield client


def run(client, name, **body):
    response = client.post('/api/run/' + name, headers=HEADERS, json=body)
    assert response.status_code == 200, response.text[:1000]
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    errors = [e for e in events if e['type'] == 'error']
    assert not errors, errors
    result = [e for e in events if e['type'] == 'result']
    assert len(result) == 1
    return result[0]


@pytest.mark.parametrize('name', [p['id'] for p in PAGES])
def test_every_page_replays_real_native_receipts(client, name):
    assert client.get('/lab/' + name).status_code == 200
    result = run(client, name)
    assert result['receipt']['mode'] == 'recorded'
    assert all(c['provenance'] == 'native-strata' for c in result['receipt']['calls'])


@pytest.mark.parametrize('name', ['choice', 'boolean', 'score'])
def test_fast_single_row_probe(client, name):
    result = run(client, name, strategy='fast')['result']
    assert result['complete']
    assert sum(row['weight'] for row in result['rows']) == pytest.approx(1)


def test_native_controller_completes_four_legal_decisions(client):
    state = 'unread'
    for expected in ['inspected', 'edited', 'verified', 'done']:
        result = run(client, 'controller', controller_state=state)['result']
        assert result['next_state'] == expected
        assert result['action'] in result['legal']
        state = result['next_state']
    assert run(client, 'controller', controller_state='done')['result']['done']


def test_threshold_changes_application_rule_without_changing_model_scores(client):
    result = run(client, 'controller', threshold=1.0)['result']
    assert result['held'] and result['next_state'] == 'unread'


def test_group_scores_and_candidate_bytes_are_consistent(client):
    result = run(client, 'candidates')['result']
    assert sum(p['weight'] for p in result['paths']) == pytest.approx(1)
    assert sum(g['weight'] for g in result['groups']) == pytest.approx(1)
    for path in result['paths']:
        assert path['text'].endswith('\n')
        assert path['logprob'] == pytest.approx(sum(t['logprob'] for t in path['tokens']))


def test_changed_inputs_cannot_silently_use_a_recording(client):
    response = client.post('/api/run/choice', headers=HEADERS, json={'state': 'Completely different private example'})
    assert response.status_code == 200
    assert 'No native recording matches these inputs' in response.text
    assert '"type": "result"' not in response.text


@pytest.mark.parametrize('page,body', [
    ('choice', {'parallel': 3}), ('wire', {'case': '../secret'}), ('graph', {'threshold': 0}),
    ('choice', {'choices': [{'label': 'A', 'description': 'one'}, {'label': 'A', 'description': 'two'}]}),
    ('candidates', {'groups': [{'name': 'one', 'answers': ['same']}, {'name': 'two', 'answers': ['same']}]}),
    ('performance', {'repeats': True}), ('performance', {'repeats': 99}),
    ('score', {'choices': [{'label': 'A', 'description': 'one'}, {'label': 'B', 'description': 'two'}]}),
    ('choice', {'state': 'x' * 3001}), ('choice', {'server_url': 'http://example.org'}),
])
def test_invalid_or_unused_options_fail_before_stream_headers(client, page, body):
    response = client.post('/api/run/' + page, headers=HEADERS, json=body)
    assert response.status_code == 422
    assert 'text/event-stream' not in response.headers['content-type']


def test_loopback_ui_rejects_cross_origin_and_unknown_host(client):
    assert client.post('/api/run/choice', json={}).status_code == 403
    assert client.post('/api/run/choice', json={}, headers={**HEADERS, 'Origin': 'http://outside.example'}).status_code == 403
    assert client.get('/', headers={'Host': 'attacker.example'}).status_code == 400


@pytest.mark.parametrize('case', ['decision', 'router', 'ambiguity', 'stream', 'grammar', 'json-schema', 'reasoning-json', 'tool-call', 'tool-result', 'selected-only'])
def test_ten_contract_examples(client, case):
    result = run(client, 'wire', case=case)['result']
    assert result['response']['choices']


def test_failed_upstream_is_a_failed_run_not_completed_output():
    async def handler(request):
        return httpx.Response(400, json={'error': {'message': 'synthetic unsupported engine'}})
    app = create_app(lambda mode: Backend('live', transport=httpx.MockTransport(handler)))
    with TestClient(app, base_url='http://localhost') as client:
        response = client.post('/api/run/choice', headers=HEADERS, json={'mode': 'live'})
    assert 'synthetic unsupported engine' in response.text
    assert '"type": "result"' not in response.text


def test_sse_error_and_missing_terminal_cannot_be_collected_as_success():
    with pytest.raises(ValueError, match='failed'):
        collect_chunks([{'error': 'synthetic broken stream'}])
    with pytest.raises(ValueError, match='terminal'):
        collect_chunks([{'choices': [{'delta': {'content': 'partial'}}]}])


def test_cancel_closes_request_local_backend():
    closed = []
    class Slow:
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): closed.append(True)
        async def call(self, body, emit): await asyncio.sleep(60)
    async def example():
        async def emit(*args): pass
        async def work():
            async with Slow() as backend:
                await run_page(Context(backend, emit), 'choice', {})
        task = asyncio.create_task(work())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(example())
    assert closed == [True]
