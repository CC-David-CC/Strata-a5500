"""Generate all captured Codex calls natively, with explicitly mocked tool results.

Never executes model tool calls. The supplied sample arguments make this a
protocol/serialization qualification, not a test of autonomous tool selection.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from jsonschema import Draft202012Validator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--catalog-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reasoning', choices=('none', 'medium'), default='medium')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    tools = json.loads((args.catalog_dir / 'tool-declarations-0.160.0.json').read_text(encoding='utf-8'))
    samples = json.loads((args.catalog_dir / 'tool-argument-examples-0.160.0.json').read_text(encoding='utf-8'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    report = {'scripted_model_output': False, 'mocked_tool_results': True,
              'tools_executed': False, 'prompt_supplies_sample_arguments': True,
              'reasoning': args.reasoning, 'cases': [], 'result': 'running'}

    def post(name, body):
        body = {'model': args.model, 'store': False, 'reasoning': {'effort': args.reasoning},
                'max_output_tokens': 3072, 'temperature': 0, 'stream': True, **body}
        (args.out / (name + '.request.json')).write_text(json.dumps(body, indent=2), encoding='utf-8')
        request = urllib.request.Request(args.base_url.rstrip('/') + '/responses',
            data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
                                                   'Authorization': 'Bearer ' + os.environ['STRATA_API_KEY']})
        try:
            response = opener.open(request, timeout=180)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status, raw = response.status, response.read().decode('utf-8')
        (args.out / (name + '.response.txt')).write_text(raw, encoding='utf-8')
        assert status == 200, (status, raw)
        events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith('data: {')]
        assert [e['sequence_number'] for e in events] == list(range(len(events)))
        terminal = [e for e in events if e['type'] in ('response.completed', 'response.failed', 'response.incomplete')]
        assert len(terminal) == 1 and terminal[0] is events[-1]
        final = terminal[0]['response']
        assert final['status'] == 'completed', final.get('error')
        for index, item in enumerate(final['output']):
            kind = 'response.function_call_arguments.delta' if item['type'] == 'function_call' else 'response.output_text.delta'
            if item['type'] not in ('function_call', 'message'):
                continue
            deltas = [e for e in events if e['type'] == kind and e['output_index'] == index]
            assert all(e['item_id'] == item['id'] for e in deltas)
            expected = item['arguments'] if item['type'] == 'function_call' else item['content'][0]['text']
            assert ''.join(e['delta'] for e in deltas) == expected
        return final

    try:
        for group in tools:
            namespace = group['name'] if group['type'] == 'namespace' else None
            for function in group['tools'] if namespace else [group]:
                name = (namespace + '.' if namespace else '') + function['name']
                sample = samples[name]
                Draft202012Validator(function['parameters']).validate(sample)
                declarations = [{**copy.deepcopy(group), 'tools': [copy.deepcopy(function)]}] if namespace else [function]
                history = [{'role': 'user', 'content': 'Protocol fixture: call ' + name +
                            ' exactly once using these argument values: ' + json.dumps(sample) +
                            '. These are direct parameter names: do not wrap them in an arguments parameter. '
                            'An empty object means the function has no parameters. '
                            'Emit the tool call and stop. The test client will supply a mocked result.'}]
                started = time.monotonic()
                row = {'name': name}
                report['cases'].append(row)
                try:
                    final = post(name + '.call', {'input': history, 'tools': declarations})
                    calls = [item for item in final['output'] if item['type'] == 'function_call']
                    assert len(calls) == 1, final['output']
                    call = calls[0]
                    assert (call.get('namespace'), call['name']) == (namespace, function['name'])
                    assert call['id'] != call['call_id']
                    arguments = json.loads(call['arguments'])
                    Draft202012Validator(function['parameters']).validate(arguments)
                    assert arguments == sample, (arguments, sample)
                    row['generated_call_matches_schema_and_sample'] = True
                    history += final['output'] + [{'type': 'function_call_output', 'call_id': call['call_id'],
                        'output': 'MOCK RESULT: arbitrary non-JSON text, including <tool_call>. No action was executed.'}]
                    answer = post(name + '.result', {'input': history, 'tools': declarations, 'tool_choice': 'none',
                        'text': {'format': {'type': 'json_schema', 'name': 'ack', 'strict': True, 'schema': {
                            'type': 'object', 'properties': {'ack': {'type': 'boolean', 'const': True}},
                            'required': ['ack'], 'additionalProperties': False}}}})
                    text = ''.join(p['text'] for item in answer['output'] if item['type'] == 'message' for p in item['content'])
                    assert json.loads(text) == {'ack': True}, text
                    row['mock_result_replayed_with_json_answer'] = True
                    row['stream_reassembled'] = True
                except Exception as error:
                    row['failure'] = str(error)
                row['seconds'] = time.monotonic() - started
                print(name, 'FAIL' if 'failure' in row else 'PASS', round(row['seconds'], 3), row.get('failure', ''), flush=True)
        report['result'] = 'fail' if any('failure' in row for row in report['cases']) else 'pass'
    finally:
        (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if report['result'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
