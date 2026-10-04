"""Bounded experiments. Model observations and code-owned state remain separate."""
import copy
import json
import math
from .client import ROOT, base_request
from .core import literal_grammar, score_content
from .control_math import (winner, move_values, thermal_next, thermal_actions, poker_values,
                           information_gain, calibration, pareto)
from .scenarios import semantic, YES_NO
from .research_ideas import IDEAS

RECIPES = {
    'Min-P → Temperature': dict(chain=['min_p','temperature'],min_p=.05,temperature=1.5),
    'Temperature → Min-P': dict(chain=['temperature','min_p'],min_p=.05,temperature=1.5),
    'Top-N-Sigma → Temperature': dict(chain=['top_n_sigma','temperature'],top_n_sigma=2,temperature=1.5),
    'XTC → Temperature': dict(chain=['top_k','min_p','xtc','temperature'],top_k=16,min_p=.04,
                             xtc_probability=.12,xtc_threshold=.15,temperature=.9),
    'Temperature → XTC': dict(chain=['top_k','min_p','temperature','xtc'],top_k=16,min_p=.04,
                             xtc_probability=.12,xtc_threshold=.15,temperature=.9),
    'XTC gate forced on': dict(chain=['top_k','min_p','xtc','temperature'],top_k=16,min_p=.04,
                             xtc_probability=1,xtc_threshold=.15,temperature=.9),
}

async def command(ctx,state,question,actions,allowed=None):
    choices=[dict(label=chr(65+i),description=text) for i,text in enumerate(actions)]
    if len(actions)==1:
        body=base_request(state+'\n'+question+'\nA: '+actions[0]+'\nReturn A.',max_tokens=4,top=5)
        body['grammar']=literal_grammar(['A'])
        output=score_content(await ctx.call('Only one legal action remains',body),'A')
        return dict(measure=None,selected=0,action=actions[0],allowed=[0],grammar=body['grammar'],output=output)
    measure=await semantic(ctx,state,question,choices)
    allowed=list(range(len(actions))) if allowed is None else list(allowed)
    if not allowed:raise ValueError('No admissible action; intervention required')
    body=base_request(measure['prompt'],max_tokens=4,top=5)
    body['grammar']=literal_grammar([choices[i]['label'] for i in allowed])
    result=score_content(await ctx.call('Select within the current state grammar',body))
    label=result['text']; index=next((i for i,c in enumerate(choices) if c['label']==label),None)
    if index not in allowed:raise ValueError('Model did not complete a legal command')
    return dict(measure=measure,selected=index,action=actions[index],allowed=allowed,grammar=body['grammar'],output=result)

async def sampler_runs(ctx,opt):
    runs=[]
    cases=[(name,profile,{}) for name,profile in RECIPES.items()]
    grammar=literal_grammar(['Hammer','Wrench','Drill'])
    cases += [
        ('GBNF + Min-P → Temperature',RECIPES['Min-P → Temperature'],{'grammar':grammar}),
        ('GBNF + XTC gate on',RECIPES['XTC gate forced on'],{'grammar':grammar}),
        ('Strict JSON + Top-N-Sigma',RECIPES['Top-N-Sigma → Temperature'],{'response_format':{
            'type':'json_schema','json_schema':{'name':'workshop_tool','strict':True,'schema':{
                'type':'object','properties':{'tool':{'enum':['Hammer','Wrench','Drill']}},
                'required':['tool'],'additionalProperties':False}}}}),
    ]
    for name,profile,constraint in cases:
        body=base_request(opt['state'],max_tokens=64 if constraint else 6,top=5);body.pop('temperature')
        body.update(constraint)
        body['strata_sampler']={**profile,'inspect':True}
        reply=await ctx.call(name,body)
        entries=reply['choices'][0]['logprobs']['content']
        if not entries or any('strata_sampling' not in t for t in entries):
            raise ValueError('This experiment requires work/samplers native ordered-host-v1 inspection')
        text=reply['choices'][0]['message']['content']
        if constraint and reply['choices'][0]['finish_reason']!='stop':
            raise ValueError('Constrained sampler output did not finish')
        if 'grammar' in constraint and text not in ['Hammer','Wrench','Drill']:
            raise ValueError('Native literal grammar did not produce a complete allowed tool')
        if 'response_format' in constraint:
            obj=json.loads(text)
            if not isinstance(obj,dict) or set(obj)!={'tool'} or obj['tool'] not in ['Hammer','Wrench','Drill']:
                raise ValueError('Native strict JSON did not match the declared schema')
        runs.append(dict(name=name,profile=profile,text=reply['choices'][0]['message']['content'],
                         tokens=entries,wall_ms=ctx.calls[-1]['wall_ms'],constraint=constraint))
    return dict(kind='samplers',runs=runs,semantics='Each run is a new generation. The six unconstrained recipes share the initial prompt. GBNF and strict JSON remove invalid continuations before sampling. Structured-output instructions can change the prompt; later tokens always depend on their own generated prefix.')

async def tictactoe(ctx,opt):
    board='X...O....';frames=[]
    for step in range(4):
        if winner(board):break
        values=move_values(board,'X'); squares=list(values)
        state='You are X in tic-tac-toe. Rows are numbered 1 through 9. Current board:\n'+'\n'.join(
            ' '.join(board[i+j] if board[i+j]!='.' else str(i+j+1) for j in range(3)) for i in (0,3,6))
        decision=await command(ctx,state,'Choose the move that wins or avoids losing.',[f'place X in square {i+1}' for i in squares])
        square=squares[decision['selected']];after=board[:square]+'X'+board[square+1:]
        frame=dict(step=step,before=board,after=after,square=square,decision=decision,
                   oracle={str(i):v for i,v in values.items()},regret=max(values.values())-values[square])
        board=after
        if not winner(board):
            other=move_values(board,'O');reply=max(other,key=lambda i:(other[i],-i))
            board=board[:reply]+'O'+board[reply+1:];frame.update(opponent_square=reply,after_opponent=board)
        frame['outcome']=winner(board);frames.append(frame)
    return dict(kind='tictactoe',frames=frames,final=board,outcome=winner(board),
                semantics='Native grammar permits empty squares. Minimax is an independent exact code oracle; the opponent uses it. No model score is treated as a win probability.')

async def chess_run(ctx,opt):
    import chess
    board=chess.Board('7k/5Q2/6K1/8/8/8/8/8 w - - 0 1')
    assert board.is_valid()
    legal=sorted(board.legal_moves,key=lambda m:m.uci());rows=[]
    for move in legal:
        san=board.san(move);board.push(move)
        rows.append(dict(uci=move.uci(),san=san,mate=board.is_checkmate(),stalemate=board.is_stalemate()))
        board.pop()
    mates=[r for r in rows if r['mate']];assert mates
    shortlist=([mates[0]]+[r for r in rows if not r['mate']][:5])
    measure=await semantic(ctx,'White to move. FEN: '+board.fen()+'\n'+str(board),
        'Which listed move immediately checkmates the black king?',
        [dict(label=chr(65+i),description=r['uci']+' ('+r['san']+')') for i,r in enumerate(shortlist)])
    body=base_request('White to move. FEN: '+board.fen()+'\nChoose the best legal move. Output only the four-character UCI move.',max_tokens=12,top=5)
    body['grammar']=literal_grammar([r['uci'] for r in rows],max_literals=256)
    chosen=score_content(await ctx.call('Generate from the complete legal-move grammar',body))
    move=chess.Move.from_uci(chosen['text']);assert move in board.legal_moves
    before=board.fen();board.push(move)
    return dict(kind='chess',before=before,after=board.fen(),legal=rows,shortlist=shortlist,measure=measure,
                chosen=chosen,mate=board.is_checkmate(),stalemate=board.is_stalemate(),grammar=body['grammar'],
                semantics='The chart scores six letter-labelled moves. The generated UCI move uses a different prompt and the full legal grammar: these are different distributions, not repeated draws from the chart. A legal result may miss mate or stalemate.')

async def poker_run(ctx,opt):
    hands=[];rates={'J':.1,'Q':.5,'K':.9}
    for card in rates:
        values=poker_values(card,rates)
        state=(f'Toy one-card poker. You hold {card}. Opponent has either remaining J,Q,K card with equal probability. '
               'Both ante 1. Check: showdown for net +1 or -1. Bet: opponent folds for your +1, or calls for showdown +2 or -2. '
               'Opponent call probabilities by card: J=.1, Q=.5, K=.9.')
        decision=await command(ctx,state,'Which action has the greatest expected chip gain?',['check','bet'])
        hands.append(dict(card=card,values=values,decision=decision,best=max(values,key=values.get),
                          regret=max(values.values())-values[decision['action']]))
    return dict(kind='poker',hands=hands,call_rates=rates,semantics='Exact utility under an explicitly supplied toy policy. Model action probabilities are neither hidden-card beliefs nor a Nash equilibrium.')

async def thermal(ctx,opt):
    temperature=70.;frames=[]
    for tick,load in enumerate([45,70,80,35,20,65]):
        allowed=thermal_actions(temperature,load);fans=[0,30,60]
        state=f'Tick {tick}. Temperature={temperature} C; load={load}. Fan choices=0,30,60. Target=60 C; hard maximum=85 C. Next temperature=T+0.22*load-0.32*fan-0.04*(T-25).'
        decision=await command(ctx,state,'Choose a fan setting to approach 60 C without crossing 85 C.',
                               [f'fan {fan}' for fan in fans],[fans.index(f) for f in allowed])
        fan=fans[decision['selected']];after=thermal_next(temperature,load,fan)
        best=min(allowed,key=lambda f:(abs(thermal_next(temperature,load,f)-60),f))
        frames.append(dict(tick=tick,temperature=temperature,load=load,fan=fan,next_temperature=after,
                           allowed=allowed,decision=decision,one_step_oracle=best,error=abs(after-60)))
        temperature=after
    # Ordinary bang-bang comparison sees the same exogenous loads.
    baseline=[];temperature=70.;fan=30
    for frame in frames:
        if temperature>65:fan=60
        elif temperature<55:fan=0
        allowed=thermal_actions(temperature,frame['load'])
        if fan not in allowed:fan=max(allowed)
        temperature=thermal_next(temperature,frame['load'],fan);baseline.append(temperature)
    return dict(kind='thermal',frames=frames,baseline=baseline,limit=85,target=60,
                semantics='Simulated dynamics, exact one-step shield, no model of disturbances or formal closed-loop stability guarantee. The baseline uses hysteresis plus the same shield.')

async def scheduler(ctx,opt):
    jobs=[dict(id='inspect',duration=2,deadline=3,after=[],meaning='read the failing test'),
          dict(id='patch',duration=4,deadline=8,after=['inspect'],meaning='repair the known bug'),
          dict(id='verify',duration=3,deadline=12,after=['patch'],meaning='run verification'),
          dict(id='docs',duration=2,deadline=5,after=[],meaning='update release notes')]
    done=[];clock=0;frames=[]
    for tick in range(4):
        pending=[j for j in jobs if j['id'] not in done]
        allowed=[i for i,j in enumerate(pending) if set(j['after'])<=set(done)]
        if len(pending)==1:
            # semantic() deliberately handles >=2 options. Last job is a code-owned forced transition.
            decision=None;pick=0
        else:
            decision=await command(ctx,f'Time {clock}. Completed {done}. Jobs: '+json.dumps(pending),
                'Which job should run next to reduce lateness while respecting dependencies?',
                [j['id']+': '+j['meaning'] for j in pending],allowed);pick=decision['selected']
        job=pending[pick];assert pick in allowed
        earliest=min((pending[i] for i in allowed),key=lambda j:(j['deadline'],j['id']))['id']
        frames.append(dict(tick=tick,clock=clock,end=clock+job['duration'],job=job,done=list(done),
                           legal=[pending[i]['id'] for i in allowed],decision=decision,earliest_deadline=earliest,
                           lateness=max(0,clock+job['duration']-job['deadline'])))
        clock+=job['duration'];done.append(job['id'])
    return dict(kind='scheduler',frames=frames,jobs=jobs,total_lateness=sum(f['lateness'] for f in frames),
                semantics='A four-job deterministic scheduling toy. The last remaining job is applied by code with zero model calls.')

async def context_run(ctx,opt):
    conditions=[('Append correction','ARCHIVE, 09:00: door=open; arm may move.\nCURRENT SENSOR, 09:01: door=closed; keep the arm stopped. Current sensor overrides the archive.'),
                ('Replace obsolete text','CURRENT SENSOR, 09:01: door=closed; keep the arm stopped.'),
                ('Inject authoritative state','CONTROLLER STATE v2: {"door":"closed","arm":"stopped","permitted":["wait"]}.')]
    choices=[dict(label='A',description='move the arm now'),dict(label='B',description='wait with the arm stopped')]
    runs=[]
    for name,state in conditions:
        measure=await semantic(ctx,state,'What action is permitted now?',choices)
        runs.append(dict(name=name,state=state,measure=measure))
    body=base_request('Current state: the door is closed. Return WAIT.',max_tokens=8,top=5)
    body['grammar']=literal_grammar(['WAIT']);repeated=[]
    for i in range(2):
        response=await ctx.call('Identical current-state request '+str(i+1),body)
        repeated.append(dict(response=response,wall_ms=ctx.calls[-1]['wall_ms']))
    return dict(kind='context',runs=runs,repeated=repeated,
                semantics='Real prompt replacement/replay through the normal API. No KV bytes are edited directly. Differences include prompt length and formatting; these are not isolated cache speedups.')

async def observer(ctx,opt):
    reports=['The request timed out. The connection closed. No successful result was returned.',
             'A patch was applied. No test has run. The deployment status is unknown.',
             'The patched service passed its tests and returned the expected result.']
    probes=['Does the report explicitly establish a failure?', 'Is verification missing or unknown?',
            'Does the report establish a successfully verified result?']
    frames=[]
    for report in reports:
        vector=[]
        for question in probes:
            measure=await semantic(ctx,report,question,YES_NO);vector.append(dict(question=question,value=measure['rows'][0]['weight'],measure=measure))
        values=[v['value'] for v in vector]
        action='inspect failure' if values[0]>.5 else 'verify' if values[1]>.5 else 'finish' if values[2]>.5 else 'ask'
        frames.append(dict(report=report,vector=vector,action=action))
    return dict(kind='observer',frames=frames,semantics='A semantic measurement vector and a disclosed threshold controller. Correlated probes are never multiplied into a claim of joint confidence.')

async def calibration_run(ctx,opt):
    fixtures=[('All three tests passed.','Did every test pass?',1),('Two tests passed; one failed.','Did every test pass?',0),
              ('The log says request cancelled before completion.','Did this request complete successfully?',0),
              ('The function returns 4 for input 2.','Does input 2 return 4?',1),
              ('The box contains only red balls.','Does the box contain a blue ball?',0),
              ('Version 2 replaced version 1; version 1 is no longer current.','Is version 2 the current version?',1)]
    rows=[]
    for state,question,truth in fixtures:
        measure=await semantic(ctx,state,question,YES_NO)
        rows.append(dict(state=state,question=question,truth=truth,probability=measure['rows'][0]['weight'],measure=measure))
    swapped=[dict(label='A',description=YES_NO[1]['description']),dict(label='B',description=YES_NO[0]['description'])]
    repeat=await semantic(ctx,fixtures[0][0],fixtures[0][1],swapped)
    return dict(kind='calibration',rows=rows,statistics=calibration(rows),
                label_swap=dict(original=rows[0]['probability'],swapped=repeat['rows'][1]['weight'],measure=repeat),
                semantics='Six disclosed teaching examples. No fitted calibration, held-out accuracy estimate or deployment guarantee.')

async def information(ctx,opt):
    faults=['power loss','blocked cooling','sensor fault'];prior=[.4,.35,.25]
    tests=[dict(name='check supply voltage',likelihood=[.95,.1,.1],cost=1),
           dict(name='inspect airflow',likelihood=[.15,.9,.15],cost=1.5),
           dict(name='compare independent sensor',likelihood=[.1,.15,.85],cost=.8)]
    for test in tests:test.update(information_gain(prior,test['likelihood']))
    chosen=max(tests,key=lambda t:t['gain_bits']/t['cost'])
    # The observed positive is a disclosed fixture, never an inference from the model.
    observation='The selected test reported its positive fault signal.'
    state=f'Possible faults: {faults}. Prior={prior}. Test={chosen["name"]}. {observation} Bayesian posterior={chosen["yes"]}.'
    decision=await command(ctx,state,'What should be inspected next?',['check power supply','clear cooling obstruction','validate or replace the faulty sensor'])
    return dict(kind='information',faults=faults,prior=prior,tests=tests,chosen=chosen,observation=observation,
                posterior=chosen['yes'],decision=decision,
                semantics='Priors, observation likelihoods and the observed test outcome are synthetic disclosed fixtures. The model action is a native answer; sensor probabilities are code-owned inputs.')

async def search(ctx,opt):
    candidates=[]
    for i,(left,right,gap) in enumerate([('circle','square',10),('square','circle',10),('circle','square',-5),
                                        ('circle','square',25),('circle','circle',10),('square','square',5)]):
        scene=dict(left_shape=left,left_color='blue',right_shape=right,right_color='gold',gap=gap)
        text=json.dumps(scene,separators=(',',':'))
        valid=gap>=0;measure=None;score=0
        if valid:
            measure=await semantic(ctx,text,'Does this scene put a blue circle to the left of a gold square without overlap?',YES_NO)
            score=measure['rows'][0]['weight']
        cost=1+abs(gap)/30+(0 if left==right else .1)
        candidates.append(dict(id=f'P{i+1}',scene=scene,program=text,valid=valid,cost=cost,score=score,measure=measure))
    valid=[c for c in candidates if c['valid']]
    return dict(kind='search',candidates=candidates,frontier=[c['id'] for c in pareto(valid)],
                semantics='Enumeration supplies six candidates; code rejects overlap. Native text probes guide a bounded utility search. The model never sees the rendered pixels.')

def analytic(name):
    if name=='sampler-sandbox':
        return dict(kind='sandbox',tokens=['repair','inspect','retry','rewrite','skip','invent','loop','garbage'],
                    logits=[4.2,3.7,2.9,2.4,1.2,.6,-.2,-2.5],
                    history=['inspect','repair','retry','inspect','repair'],
                    semantics='Synthetic finite distribution. Every token is shown; this is not a truncated native top-N row. DRY-like and surprise-feedback modes teach mechanisms and are not advertised native implementations.')
    if name=='frontier':
        evidence=json.loads((ROOT/'docs/sampler-evidence/oracle.json').read_text(encoding='utf-8'))
        return dict(kind='frontier',measurements=evidence['cases'],vocabulary=248320,bytes_per_logit=4,
                    semantics='Selection times are actual native CPU measurements. Bandwidth, power, forward-pass duration and price controls are assumptions for a lower-bound calculation, not measured hardware telemetry.')
    branches=[
        ('Observe','Semantic vectors → fault observers → belief-state control','observer','Native probes','Compare observability and calibration with lexical and supervised baselines.'),
        ('Constrain','State → legal action grammar → verified transition','tictactoe','Native GBNF + code oracle','Measure strategy regret separately from legal-move rate.'),
        ('Search','Candidate trees → whole-path scoring → shared-prefix replay','candidates','Finite native paths','Account for EOS, tokenization and unmeasured residual language mass.'),
        ('Shape','Cold support → heat → exploration → feedback','samplers','Native priority recipes','Move selection to GPU without changing same-tensor probabilities.'),
        ('Rewrite','Authoritative state → new prompt → cache-aware re-prefill','context','Ordinary API intervention','Instrument prefix reuse and recurrent-state correctness; no arbitrary KV edit claim.'),
        ('Inspect','Information gain → targeted observation → updated belief','information','Analytic belief model + native action','Learn observation likelihoods and compare cost-sensitive policies.'),
        ('Reconstruct','Immutable blocks → weighted edges → admissible graph','graph','Native estimates + exact small solver','Preserve alternatives; test global structure against labeled source documents.'),
        ('Optimize','Semantics → hard checks → Pareto search','search','Bounded native-scored search','Evaluate actual rendered outputs with independent human or visual judgments.'),
        ('Compress','Probe vectors → retrieval keys → semantic monitoring','observer','Research extension','Measure loss of sufficient state and drift rather than assuming a perfect embedding.'),
        ('Explore odd uses','Music rules · robot plans · circuit sketches · proof tactics','research-map','Unimplemented research ideas','Choose a checkable domain; separate grammar validity from physics, truth or usefulness.'),
        ('Accelerate','GPU score gather → prefix sharing → batching → adaptive MTP','frontier','Optimization proposals','Measure bytes, arithmetic, verified output and quality under equal budgets.'),
        ('Steer mid-generation','Acknowledge token → new grammar → rollback uncommitted drafts','research-map','Separate endpoint design needed','Specify committed-prefix boundaries, stale commands, cancellation and replay before coding.'),
    ]
    return dict(kind='research-map',branches=[dict(name=a,path=b,page=c,status=d,gate=e) for a,b,c,d,e in branches]+IDEAS,
                semantics='An explicit experiment tree, not a claim to exhaust every application or to have achieved the proposed optimizations.')

async def run_research(ctx,name,opt):
    if name in ('sampler-sandbox','frontier','research-map'):return analytic(name)
    handlers={'samplers':sampler_runs,'tictactoe':tictactoe,'chess':chess_run,'poker':poker_run,
              'thermal':thermal,'scheduler':scheduler,'context':context_run,'observer':observer,
              'calibration':calibration_run,'information':information,'search':search}
    return await handlers[name](ctx,opt)
