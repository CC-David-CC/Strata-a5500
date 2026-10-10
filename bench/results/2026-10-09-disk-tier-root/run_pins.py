import json, subprocess, sys, time, traceback
from pathlib import Path
r=Path(__file__).resolve().parent
state={'phase':'waiting for matrix','runs':[]}
def save(): (r/'pins-status.json').write_text(json.dumps(state,indent=2))
save()
try:
    while json.loads((r/'matrix-status.json').read_text()).get('phase') not in ['complete','failed']:
        time.sleep(2)
    for candidate in [True,False]:
        config=r/('candidate-config.json' if candidate else 'baseline-config.json')
        for mode in ['disk','ram','ram-fallback']:
            name=('candidate-' if candidate else 'baseline-')+'effective-pin-'+mode
            state['phase']=name;save()
            args=[sys.executable,str(r/'probe_effective_pin.py'),'--source',str(r/'source'),'--config',str(config),
                  '--output',str(r/name),'--mtp','/home/dflanag3/Strata-data/mtp/rt','--cache-mode',mode]
            if not candidate:args+=['--only-mtp']
            with (r/(name+'.log')).open('w') as f:
                subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
            state['runs'].append({'name':name,**json.loads((r/name/'complete.json').read_text())})
    state.update(phase='complete',finished=time.time())
except BaseException:
    state.update(phase='failed',error=traceback.format_exc())
finally:save()
