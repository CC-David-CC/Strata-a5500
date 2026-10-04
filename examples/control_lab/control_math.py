"""Small transparent plants, oracles and scoring rules. No model or HTTP calls."""
import math
from functools import lru_cache

LINES=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
def winner(board):
    for a,b,c in LINES:
        if board[a]!='.' and board[a]==board[b]==board[c]:return board[a]
    return 'draw' if '.' not in board else None

@lru_cache(None)
def minimax(board,turn):
    end=winner(board)
    if end:return 0 if end=='draw' else (1 if end==turn else -1)
    other='O' if turn=='X' else 'X'
    return max(-minimax(board[:i]+turn+board[i+1:],other) for i,v in enumerate(board) if v=='.')

def move_values(board,turn):
    if winner(board):return {}
    other='O' if turn=='X' else 'X'
    return {i:-minimax(board[:i]+turn+board[i+1:],other) for i,v in enumerate(board) if v=='.'}

def thermal_next(temperature,load,fan):
    return round(temperature+.22*load-.32*fan-.04*(temperature-25),3)

def thermal_actions(temperature,load,limit=85):
    return [fan for fan in [0,30,60] if thermal_next(temperature,load,fan)<=limit]

def poker_values(card,call_rates=None):
    # One-card toy game: ante 1 each. Check shows cards (+/-1); a bet adds 1.
    # Opponent folds (+1) or calls (winner +/-2). Conditional hidden-card prior uniform.
    rates=call_rates or {'J':.1,'Q':.5,'K':.9}
    rank={'J':0,'Q':1,'K':2}; others=[c for c in rank if c!=card]
    check=math.fsum(1 if rank[card]>rank[o] else -1 for o in others)/2
    bet=math.fsum((1-rates[o])+rates[o]*(2 if rank[card]>rank[o] else -2) for o in others)/2
    return {'check':check,'bet':bet}

def entropy(weights):return -math.fsum(p*math.log2(p) for p in weights if p>0)
def information_gain(prior,likelihood):
    p_yes=math.fsum(p*l for p,l in zip(prior,likelihood))
    yes=[p*l/p_yes for p,l in zip(prior,likelihood)] if p_yes else list(prior)
    no=[p*(1-l)/(1-p_yes) for p,l in zip(prior,likelihood)] if p_yes<1 else list(prior)
    gain=entropy(prior)-p_yes*entropy(yes)-(1-p_yes)*entropy(no)
    return dict(p_yes=p_yes,yes=yes,no=no,gain_bits=gain)

def calibration(rows):
    brier=math.fsum((r['probability']-r['truth'])**2 for r in rows)/len(rows)
    bins=[]
    for i in range(5):
        members=[r for r in rows if min(4,int(r['probability']*5))==i]
        if members:bins.append(dict(low=i/5,high=(i+1)/5,count=len(members),
            predicted=math.fsum(r['probability'] for r in members)/len(members),
            observed=math.fsum(r['truth'] for r in members)/len(members)))
    return dict(brier=brier,bins=bins,n=len(rows))

def pareto(rows):
    return [r for r in rows if not any(s['cost']<=r['cost'] and s['score']>=r['score'] and
        (s['cost']<r['cost'] or s['score']>r['score']) for s in rows)]
