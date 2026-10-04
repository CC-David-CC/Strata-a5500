"""Math and controller invariants; all invented scores here are synthetic tests."""
import math

import pytest

from .core import (admissible_graph, advance_state, allowed_actions, distribution_stats,
                   literal_grammar, logsumexp, normalized_weights, reconstruct_graph,
                   score_content, top_row_distribution, validate_groups)


def reply(text='A', entries=None):
    if entries is None:
        entries = [dict(token=text, bytes=list(text.encode()), logprob=math.log(.4), top_logprobs=[
            dict(token='A', bytes=[65], logprob=math.log(.4)),
            dict(token='<eos>', bytes=None, logprob=math.log(.2))])]
    return {'choices': [{'message': {'content': text}, 'finish_reason': 'stop', 'logprobs': {'content': entries}}]}


def test_underflow_does_not_destroy_relative_path_weights():
    assert normalized_weights([-10001, -10000]) == pytest.approx([.26894142137, .73105857863])
    assert logsumexp([math.log(.2), math.log(.3)]) == pytest.approx(math.log(.5))


@pytest.mark.parametrize('values', [[], [math.inf], [math.nan], [-math.inf]])
def test_invalid_logps_are_not_silently_normalized(values):
    with pytest.raises(ValueError):
        normalized_weights(values)


def test_group_probability_is_sum_not_mean_and_is_stable():
    paths = [math.log(.2), math.log(.3), math.log(.1)]
    assert normalized_weights([logsumexp(paths[:2]), paths[2]]) == pytest.approx([5/6, 1/6])


def test_label_outside_topn_stays_unknown_and_special_tokens_are_not_labels():
    data = top_row_distribution(reply(), ['A', 'B'])
    assert not data['complete'] and data['missing'] == ['B']
    assert data['raw_logprobs'][1] is None
    assert 'weights' not in data


def test_selected_token_is_scored_even_outside_topn():
    entries = [dict(token='Z', bytes=[90], logprob=-14, top_logprobs=[dict(token='A', bytes=[65], logprob=-.1)])]
    data = top_row_distribution(reply('Z', entries), ['A', 'Z'])
    assert data['complete']
    assert data['raw_logprobs'] == [-.1, -14]


def test_scores_follow_original_utf8_bytes_and_not_retokenized_strings():
    entries = [dict(token='�', bytes=[195], logprob=-1, top_logprobs=[]),
               dict(token='�', bytes=[169], logprob=-2, top_logprobs=[])]
    result = score_content(reply('é', entries), 'é')
    assert result['logprob'] == -3
    with pytest.raises(ValueError, match='exact answer'):
        score_content(reply('e', entries))
    with pytest.raises(ValueError, match='Incomplete'):
        score_content(reply(), 'AB')


def test_grammar_escapes_quotes_newlines_and_unicode():
    assert literal_grammar(['say "hi"\n', 'é']) == 'root ::= "say \\"hi\\"\\n" | "é"'.replace('\\\\"', '\\"')


def test_overlapping_finite_languages_are_rejected_not_double_counted():
    with pytest.raises(ValueError, match='Overlapping'):
        validate_groups([dict(name='one', answers=['A']), dict(name='two', answers=['A'])])
    with pytest.raises(ValueError, match='newlines'):
        validate_groups([dict(name='one', answers=['A\n']), dict(name='two', answers=['B'])])


def test_derived_confidence_and_score_are_calculations_not_extra_evidence():
    a = distribution_stats([.6, .3, .1], [0, .5, 1])
    b = distribution_stats([.6, .2, .2])
    assert a['peakedness'] == pytest.approx(.4)
    assert a['peakedness'] == b['peakedness']
    assert a['expected_score'] == pytest.approx(.25)
    assert a['entropy_bits'] != b['entropy_bits']


def test_controller_cannot_finish_before_verification():
    state = 'unread'
    for action in ['inspect', 'edit', 'test', 'finish']:
        if state != 'verified':
            with pytest.raises(ValueError):
                advance_state(state, 'finish')
        state = advance_state(state, action)
    assert state == 'done' and not allowed_actions(state)
    with pytest.raises(ValueError):
        advance_state('done', 'inspect')


def edge(a, b, weight, relation='continues'):
    return dict(source=a, target=b, weight=weight, relation=relation)


def test_graph_solver_avoids_cycle_and_keeps_only_one_caption_target():
    edges = [edge('A', 'B', .95), edge('B', 'C', .9), edge('C', 'A', .8),
             edge('caption', 'A', .9, 'caption'), edge('caption', 'B', .8, 'caption')]
    result = reconstruct_graph(edges)
    assert result['selected'] == [edges[0], edges[1], edges[3]]
    assert result['evaluated_subsets'] == 32
    assert admissible_graph(result['selected'])
    assert not admissible_graph(edges)


def test_graph_global_selection_beats_greedy_local_edge_choice():
    edges = [edge('A', 'B', .9), edge('A', 'C', .8), edge('D', 'B', .8)]
    assert reconstruct_graph(edges)['selected'] == edges[1:]


def test_graph_retains_uncertain_alternatives_in_original_input():
    edges = [edge('A', 'B', .49), edge('A', 'C', .51)]
    assert reconstruct_graph(edges)['selected'] == [edges[1]]
    assert len(edges) == 2


def test_controller_legal_conditioning_survives_tiny_raw_mass(monkeypatch):
    import asyncio
    from . import scenarios
    async def measured(*args):
        return {'prompt': 'synthetic underflow fixture', 'rows': [
            {'label': label, 'logprob': lp, 'weight': math.exp(lp)}
            for label, lp in zip('ABCDE', [-1002, 0, -2000, -2000, -1001])]}
    class Context:
        async def call(self, *args):
            return reply('A', [dict(token='A', bytes=[65], logprob=-1002, top_logprobs=[])])
    monkeypatch.setattr(scenarios, 'semantic', measured)
    result = asyncio.run(scenarios.run_controller(Context(), {'controller_state': 'unread', 'state': 'synthetic', 'threshold': 0}))
    assert result['legal_conditional_weight'] == pytest.approx(.26894142137)
    assert result['next_state'] == 'inspected'
