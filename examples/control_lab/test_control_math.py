"""Pure oracle properties and native-receipt closed-loop invariants."""
import json
from pathlib import Path
import pytest
from .control_math import (winner,minimax,move_values,thermal_next,thermal_actions,poker_values,
                           information_gain,calibration,pareto)

EVIDENCE=Path(__file__).resolve().parents[2]/'docs/control-lab-evidence'
def recorded(name):return json.loads((EVIDENCE/(name+'.json')).read_text(encoding='utf-8'))['result']

def test_all_reachable_tictactoe_states_and_symmetry():
    seen=set()
    def visit(board,turn):
        if (board,turn) in seen:return
        seen.add((board,turn))
        reflected=''.join(board[r*3+c] for r in range(3) for c in [2,1,0])
        assert minimax(board,turn)==minimax(reflected,turn)
        if winner(board):return
        vals=move_values(board,turn)
        assert minimax(board,turn)==max(vals.values())
        other='O' if turn=='X' else 'X'
        for pos in vals:visit(board[:pos]+turn+board[pos+1:],other)
    visit('.'*9,'X')
    assert len(seen)==5478
    assert minimax('.'*9,'X')==0

def test_native_game_only_applies_legal_moves_and_keeps_oracle_separate():
    data=recorded('tictactoe');board='X...O....'
    for frame in data['frames']:
        assert frame['before']==board and board[frame['square']]=='.'
        assert frame['regret']==max(move_values(board,'X').values())-move_values(board,'X')[frame['square']]
        board=frame.get('after_opponent',frame['after'])
    assert board==data['final'] and winner(board)==data['outcome']

def test_thermal_shield_and_no_admissible_action():
    for temperature in range(25,101,5):
        for load in range(0,101,5):
            allowed=thermal_actions(temperature,load)
            assert set(allowed)=={fan for fan in (0,30,60) if thermal_next(temperature,load,fan)<=85}
    assert thermal_actions(100,100)==[]
    for frame in recorded('thermal')['frames']:
        assert frame['fan'] in thermal_actions(frame['temperature'],frame['load'])
        assert frame['next_temperature']==thermal_next(frame['temperature'],frame['load'],frame['fan'])
        assert frame['next_temperature']<=85

def test_poker_is_utility_under_a_named_policy():
    assert poker_values('J')==pytest.approx({'check':-1,'bet':-1.1})
    assert poker_values('Q')==pytest.approx({'check':0,'bet':-.3})
    assert poker_values('K')==pytest.approx({'check':1,'bet':1.3})
    assert poker_values('J',{'J':0,'Q':0,'K':0})['bet']==1

def test_information_gain_limits_and_posterior():
    exact=information_gain([.5,.5],[1,0]);assert exact['gain_bits']==1 and exact['yes']==[1,0]
    empty=information_gain([.5,.5],[.3,.3]);assert empty['gain_bits']==pytest.approx(0)
    assert information_gain([1,0],[1,0])['gain_bits']==0
    for test in recorded('information')['tests']:
        assert sum(test['yes'])==pytest.approx(1) and sum(test['no'])==pytest.approx(1)
        assert test['gain_bits']>=0

def test_proper_score_and_pareto():
    assert calibration([{'probability':.8,'truth':1},{'probability':.2,'truth':0}])['brier']==pytest.approx(.04)
    rows=[dict(cost=1,score=.5),dict(cost=2,score=.6),dict(cost=3,score=.4)]
    assert pareto(rows)==rows[:2]

def test_native_scheduler_respects_dependencies():
    data=recorded('scheduler');done=set();clock=0
    for frame in data['frames']:
        job=frame['job'];assert set(job['after'])<=done and frame['clock']==clock
        assert job['id'] in frame['legal'];done.add(job['id']);clock+=job['duration']
    assert len(done)==len(data['jobs'])

def test_chess_full_legal_grammar_and_proof():
    import chess
    data=recorded('chess');board=chess.Board(data['before'])
    assert {m.uci() for m in board.legal_moves}=={r['uci'] for r in data['legal']}
    for row in data['legal']:
        board.push_uci(row['uci']);assert board.is_checkmate()==row['mate'];board.pop()
    board.push_uci(data['chosen']['text']);assert board.fen()==data['after']

def test_native_sampler_receipts_use_all_stage_statistics():
    for run in recorded('samplers')['runs']:
        for token in run['tokens']:
            receipt=token['strata_sampling']
            assert [s['operator'] for s in receipt['stages']]==['grammar']+run['profile']['chain']
            assert receipt['support']==receipt['stages'][-1]['support']
            assert receipt['probability']>0
    assert recorded('samplers')['runs'][0]['tokens'][0]['strata_sampling']['stages'][0]['support']==248320


def test_native_sampler_combines_grammar_and_strict_json():
    runs=recorded('samplers')['runs']
    assert len(runs)==9
    for run in runs[6:]:
        if 'grammar' in run['constraint']:
            assert run['text'] in ['Hammer','Wrench','Drill']
        else:
            obj=json.loads(run['text'])
            assert set(obj)=={'tool'} and obj['tool'] in ['Hammer','Wrench','Drill']
        assert run['tokens'][0]['strata_sampling']['stages'][0]['support']<248320
