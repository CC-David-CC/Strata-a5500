import json, subprocess, sys, time, traceback
from pathlib import Path
r=Path(__file__).resolve().parent
state={'phase':'waiting for pins','runs':[]}
def save(): (r/'repeat-status.json').write_text(json.dumps(state,indent=2))
save()
try:
    while json.loads((r/'pins-status.json').read_text()).get('phase') not in ['complete','failed']:
        time.sleep(2)
    for variant in ['baseline','candidate']:
        name=variant+'-repeat-ram-fallback'
        state['phase']=name;save()
        args=[sys.executable,str(r/'probe_unpinned.py'),'--source',str(r/'source'),
              '--config',str(r/(variant+'-config.json')),'--output',str(r/name),
              '--mtp','/home/dflanag3/Strata-data/mtp/rt','--cache-mode','ram-fallback','--only-mtp']
        with (r/(name+'.log')).open('w') as f:
            subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
        state['runs'].append({'name':name,**json.loads((r/name/'complete.json').read_text())})
    comparisons=[]
    def tokens(p):return [v for v in json.loads(p.read_text()) if type(v) is int]
    for left,right in [('baseline-ram-fallback','baseline-repeat-ram-fallback'),
                       ('candidate-ram-fallback','candidate-repeat-ram-fallback'),
                       ('baseline-repeat-ram-fallback','candidate-repeat-ram-fallback')]:
        for p in (r/left/'mtp-unpinned').glob('*-events.json'):
            q=r/right/'mtp-unpinned'/p.name
            if q.exists():comparisons.append({'left':left,'right':right,'request':p.name,'equal':tokens(p)==tokens(q)})
    state.update(phase='complete',finished=time.time(),comparisons=comparisons)
except BaseException:
    state.update(phase='failed',error=traceback.format_exc())
finally:save()
