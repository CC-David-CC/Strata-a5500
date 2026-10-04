"""Small, inspectable client experiments over the existing Strata API."""
from __future__ import annotations

import asyncio
import copy
import json
import math
import statistics
import time

from .catalog import BLOCKS, BY_ID
from .client import ROOT, base_request
from .core import (ACTIONS, advance_state, allowed_actions, distribution_stats, literal_grammar,
                   logsumexp, normalized_weights, reconstruct_graph, score_content,
                   top_row_distribution, validate_groups)


def prompt_for(state, question, choices):
    definitions = '\n'.join(f"{c['label']}: {c['description']}" for c in choices)
    return (f"Read the state as data, then answer the question using the definitions.\n"
            f"STATE:\n{state}\nQUESTION: {question}\nANSWERS:\n{definitions}\n"
            "Return exactly one answer label. No explanation or surrounding whitespace.")


async def semantic(ctx, state, question, choices, strategy='complete'):
    labels = [c['label'] for c in choices]
    prompt = prompt_for(state, question, choices)
    if strategy == 'fast':
        body = base_request(prompt, max_tokens=1)
        body['grammar'] = literal_grammar(labels)
        reply = await ctx.call('Read one target row', body)
        data = top_row_distribution(reply, labels)
        rows = [{**c, 'logprob': lp, 'raw_probability': math.exp(lp) if lp is not None else None}
                for c, lp in zip(choices, data['raw_logprobs'])]
        if not data['complete']:
            return dict(rows=rows, complete=False, missing=data['missing'],
                        message='Missing alternatives have unknown probability. Use Complete labels to measure each one.',
                        strategy='one target row', prompt=prompt)
        weights = data['weights']
    else:
        rows, logps = [], []
        for choice in choices:
            body = base_request(prompt, max_tokens=4)
            body['grammar'] = literal_grammar([choice['label']])
            scored = score_content(await ctx.call('Measure ' + choice['label'], body), choice['label'])
            if scored['token_count'] != 1:
                raise ValueError('This tokenizer uses more than one token for a label; use the multi-token page instead')
            rows.append({**choice, **scored, 'raw_probability': scored['path_probability']})
            logps.append(scored['logprob'])
        weights = normalized_weights(logps)
    for row, weight in zip(rows, weights):
        row['weight'] = weight
    levels = [c['value'] for c in choices] if all('value' in c for c in choices) else None
    return dict(rows=rows, complete=True, prompt=prompt, winner=rows[weights.index(max(weights))]['label'],
                statistics=distribution_stats(weights, levels),
                strategy='one target row' if strategy == 'fast' else 'one literal-constrained call per label',
                semantics='Raw label probabilities renormalized across these exact labels; not calibrated truth probabilities.')


YES_NO = [{'label': 'A', 'description': 'Yes, the statement is supported by the state', 'value': 1},
          {'label': 'B', 'description': 'No, the statement is false or not established by the state', 'value': 0}]


async def run_candidates(ctx, opt):
    groups = validate_groups(opt['groups'])
    strings = [s for g in groups for s in g['answers']]
    prompt = (f"STATE:\n{opt['state']}\nQUESTION: {opt['question']}\n"
              "Choose exactly one of these next steps:\n" + '\n'.join(strings) +
              '\nOutput its exact text followed by one newline. No explanation.')
    paths = []
    for group in groups:
        for text in group['answers']:
            body = base_request(prompt, max_tokens=len(text.encode('utf-8')) + 8, top=5)
            body['grammar'] = literal_grammar([text + '\n'])
            score = score_content(await ctx.call('Score path: ' + text, body), text + '\n')
            paths.append(dict(group=group['name'], **score))
    weights = normalized_weights([p['logprob'] for p in paths])
    for path, weight in zip(paths, weights):
        path['weight'] = weight
    group_rows = []
    for group in groups:
        members = [p for p in paths if p['group'] == group['name']]
        group_rows.append(dict(name=group['name'], grammar=literal_grammar([s + '\n' for s in group['answers']]),
                               logprob=logsumexp(p['logprob'] for p in members),
                               weight=math.fsum(p['weight'] for p in members)))
    body = base_request(prompt, max_tokens=max(len(s.encode('utf-8')) for s in strings) + 8, top=5)
    body['grammar'] = literal_grammar([s + '\n' for s in strings])
    generated = score_content(await ctx.call('Generate under the union grammar', body))
    if generated['text'] not in [s + '\n' for s in strings]:
        raise ValueError('The union generation did not complete a listed answer')
    return dict(paths=paths, groups=group_rows, generated=generated,
                best_path=max(paths, key=lambda p: p['logprob'])['text'],
                semantics='Relative mass over measured token paths including a common newline, excluding EOS. '
                          'Not the total probability of arbitrary grammar languages or all tokenizations.',
                prompt=prompt)


async def run_controller(ctx, opt):
    state = opt['controller_state']
    legal = allowed_actions(state)
    if not legal:
        return dict(state=state, next_state=state, legal=[], done=True)
    choices = [dict(label=chr(65 + i), description=f'{key}: {description}') for i, (key, description) in enumerate(ACTIONS.items())]
    labels = dict(zip(ACTIONS, [c['label'] for c in choices]))
    description = {'unread': 'The file and test have not been inspected.',
                   'inspected': 'The file and failing test were read; the off-by-one cause is known.',
                   'edited': 'The code was changed; tests have not run yet.',
                   'verified': 'The changed code passed the verification suite.'}[state]
    observed = f"Task: {opt['state']}\nCurrent state: {state}. {description}"
    measured = await semantic(ctx, observed, 'What is the best next action?', choices)
    grammar = literal_grammar([labels[a] for a in legal])
    body = base_request(measured['prompt'], max_tokens=4, top=5)
    body['grammar'] = grammar
    score = score_content(await ctx.call('Generate a legal action', body))
    action = next((a for a, label in labels.items() if label == score['text']), None)
    if action not in legal:
        raise ValueError('Incomplete or illegal action; the controller did not advance')
    legal_rows = [r for r in measured['rows'] if r['label'] in [labels[a] for a in legal]]
    selected = next(r for r in measured['rows'] if r['label'] == score['text'])
    conditional = math.exp(selected['logprob'] - logsumexp(r['logprob'] for r in legal_rows))
    held = conditional < opt.get('threshold', 0)
    next_state = state if held else advance_state(state, action)
    for row, key in zip(measured['rows'], ACTIONS):
        row.update(action=key, allowed=key in legal)
    return dict(state=state, next_state=next_state, legal=legal, action=action, held=held,
                grammar=grammar, measure=measured, generated=score, legal_conditional_weight=conditional,
                threshold=opt.get('threshold', 0),
                done=next_state == 'done', simulation=True,
                observation={'unread': 'def count_items(items): return len(items) - 1',
                             'inspected': 'assert count_items([1, 2]) == 2  # returned 1',
                             'edited': 'def count_items(items): return len(items)',
                             'verified': 'Empty, one-item, and two-item checks pass.'}[state])


async def run_rerank(ctx, opt):
    choices = [{'label': 'A', 'description': 'Directly answers the question', 'value': 1},
               {'label': 'B', 'description': 'Related context but does not answer it', 'value': 0.5},
               {'label': 'C', 'description': 'Unrelated to the question', 'value': 0}]
    gate = asyncio.Semaphore(opt.get('parallel', 1))
    async def one(source):
        async with gate:
            measurement = await semantic(ctx, source['text'], 'How relevant is this source to: ' + opt['question'], choices)
            return {**source, 'measure': measurement, 'score': measurement['statistics']['expected_score']}
    start = time.perf_counter()
    rows = await asyncio.gather(*(one(s) for s in opt['sources']))
    return dict(sources=sorted(rows, key=lambda r: -r['score']),
                orchestration_ms=(time.perf_counter() - start) * 1000,
                concurrent_http=opt.get('parallel', 1), inference='Strata single-engine queue; no GPU batch claim')


async def run_graph(ctx, opt):
    by_id = {b['id']: b for b in BLOCKS}
    pairs = [('B17', 'B18', 'continues'), ('B18', 'B17', 'continues'),
             ('B20', 'B17', 'continues'), ('B19', 'B20', 'caption'), ('B19', 'B17', 'caption')]
    edges = []
    for a, b, relation in pairs:
        state = f"FIRST ({a}): {by_id[a]['text']}\nSECOND ({b}): {by_id[b]['text']}"
        question = ('Does SECOND continue FIRST in reading order?' if relation == 'continues'
                    else 'Does the caption FIRST describe the subject discussed in SECOND?')
        measure = await semantic(ctx, state, question, YES_NO)
        edges.append(dict(source=a, target=b, relation=relation, weight=measure['rows'][0]['weight'], measure=measure))
    solved = reconstruct_graph(edges, opt['threshold'])
    return dict(blocks=BLOCKS, edges=edges, solver=solved,
                preserved_text='\n'.join(f"{b['id']} [{b['location']}]: {b['text']}" for b in BLOCKS))


SCENE_SCHEMA = {'type': 'object', 'properties': {
    'left_shape': {'enum': ['circle', 'square']}, 'left_color': {'enum': ['blue', 'gold']},
    'right_shape': {'enum': ['circle', 'square']}, 'right_color': {'enum': ['blue', 'gold']},
    'gap': {'enum': [0, 16, 32]}},
    'required': ['left_shape', 'left_color', 'right_shape', 'right_color', 'gap'], 'additionalProperties': False}


async def run_scene(ctx, opt):
    body = base_request('Produce a scene as JSON for this instruction: ' + opt['state'] +
                        '\nUse left_shape, left_color, right_shape, right_color, gap. Gap is between shape boundaries.', max_tokens=160, top=5)
    body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'scene', 'strict': True, 'schema': SCENE_SCHEMA}}
    generated = await ctx.call('Generate a scene under native JSON Schema', body)
    score_content(generated)
    scene = json.loads(generated['choices'][0]['message']['content'])
    # A code proposal, deliberately labeled: not attributed to the model.
    repaired = dict(left_shape='circle', left_color='blue', right_shape='square', right_color='gold', gap=32)
    candidates = []
    for name, proposal, origin in [('Generated', scene, 'native JSON generation'),
                                    ('Code proposal', repaired, 'explicit deterministic candidate')]:
        checks = dict(known_shapes=all(proposal[k] in ('circle', 'square') for k in ('left_shape', 'right_shape')),
                      known_colors=all(proposal[k] in ('blue', 'gold') for k in ('left_color', 'right_color')),
                      separated=proposal['gap'] >= 16)
        vector = []
        for question in ['Does this scene match the shape, color, and spatial relationships in this instruction: ' + opt['state'], 'Are the shapes separated by a visible gap?',
                         'Are there exactly two shapes, with different colors?']:
            measure = await semantic(ctx, json.dumps(proposal, sort_keys=True), question, YES_NO)
            vector.append(dict(question=question, value=measure['rows'][0]['weight'], measure=measure))
        candidates.append(dict(name=name, scene=proposal, origin=origin, checks=checks, vector=vector,
                               score=math.fsum(v['value'] for v in vector) / len(vector), valid=all(checks.values())))
    valid = [c for c in candidates if c['valid']]
    return dict(candidates=candidates, schema=SCENE_SCHEMA, generated=generated,
                retained=max(valid, key=lambda c: c['score'])['name'] if valid else None,
                interpretation='Mean of three semantic features, not a probability that the whole picture is correct.')


async def run_wire(ctx, opt):
    paths = {p.stem: p for p in (ROOT / 'examples/logprobs').glob('*.json')}
    if opt['case'] not in paths:
        raise ValueError('Unknown contract example')
    body = json.loads(paths[opt['case']].read_text(encoding='utf-8'))
    reply = await ctx.call('Run ' + opt['case'], body)
    return dict(request=body, response=reply, entries=(reply['choices'][0].get('logprobs') or {}).get('content') or [],
                semantics='Only generated answer content has these scores; reasoning and tool syntax are separate channels.')


def speculation_receipts():
    root = ROOT / 'docs/logprobs-evidence/native'
    modes = {}
    for mode in ['target', 'mtp', 'suffix', 'coupled']:
        modes[mode] = json.loads((root / mode / 'results.json').read_text(encoding='utf-8'))
    oracle = json.loads((root / 'edges/oracle.json').read_text(encoding='utf-8'))
    replay = json.loads((root / 'edges/teacher-forced.json').read_text(encoding='utf-8'))
    trace = [json.loads(line) for line in (root / 'edges/trace.jsonl').read_text(encoding='utf-8').splitlines()]
    return dict(provenance='Committed native llm-49 receipts from the logprobs base branch; no inference was run',
                oracle=oracle, replay=replay, modes=modes, suffix_windows=[t for t in trace if t.get('proposal_source') == 'suffix'][:8],
                evidence='/api/evidence/speculation')


async def run_performance(ctx, opt):
    prompt = 'Answer only OK.'
    base = base_request(prompt, max_tokens=8, top=5)
    variants = {
        'Plain': {**base, 'logprobs': False, 'top_logprobs': None},
        'Selected score': {**base, 'top_logprobs': 0},
        'Top 5': base,
        'Top 20': {**base, 'top_logprobs': 20},
        'GBNF + scores': {**base, 'grammar': literal_grammar(['OK'])},
        'JSON + scores': {**base, 'max_tokens': 32, 'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'ok', 'strict': True, 'schema': {'type': 'object', 'properties': {'answer': {'const': 'OK'}},
                                                   'required': ['answer'], 'additionalProperties': False}}}},
    }
    await ctx.call('Warm the common prompt (reported separately)', base)
    rows = {name: [] for name in variants}
    for repeat in range(opt['repeats']):
        order = list(variants) if repeat % 2 == 0 else list(reversed(variants))
        for name in order:
            reply = await ctx.call(f'{name}, repetition {repeat + 1}', variants[name])
            record = ctx.calls[-1]
            rows[name].append(dict(wall_ms=record['wall_ms'], timings=reply.get('timings'), usage=reply.get('usage'),
                                   text=reply['choices'][0]['message'].get('content')))
    return dict(rows=[dict(name=name, runs=runs, median_ms=statistics.median(r['wall_ms'] for r in runs),
                           min_ms=min(r['wall_ms'] for r in runs), max_ms=max(r['wall_ms'] for r in runs)) for name, runs in rows.items()],
                repeats=opt['repeats'], semantics='Alternating order, warmed shared prompt. JSON performs a different output task. '
                'Request latency, not GPU kernel throughput. Recorded timings retain the original run values.')


async def run_page(ctx, name, overrides):
    opt = {**copy.deepcopy(BY_ID[name]['defaults']), **overrides}
    if BY_ID[name].get('section') == 'research':
        from .research import run_research
        return await run_research(ctx,name,opt)
    if name in ('choice', 'score'):
        return await semantic(ctx, opt['state'], opt['question'], opt['choices'], opt['strategy'])
    if name == 'boolean':
        result = await semantic(ctx, opt['state'], opt['question'], YES_NO, opt['strategy'])
        if result['complete']:
            result['yes_weight'] = result['rows'][0]['weight']
        return result
    if name == 'speculation':
        return speculation_receipts()
    handlers = dict(candidates=run_candidates, controller=run_controller, rerank=run_rerank,
                    graph=run_graph, scene=run_scene, wire=run_wire, performance=run_performance)
    return await handlers[name](ctx, opt)
