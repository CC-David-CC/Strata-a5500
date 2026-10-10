import hashlib, json, subprocess, sys, time, traceback
from pathlib import Path
r=Path(__file__).resolve().parent
state={'started':time.time(),'runs':[]}
def run(name,args):
    state['phase']=name
    (r/'matrix-status.json').write_text(json.dumps(state,indent=2))
    with (r/(name+'.log')).open('w') as f:
        subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
try:
    run('candidate-unit-tests',['ctest','--test-dir',str(r/'build'),'--output-on-failure','-R','^conversation_(spill|file|validation|snapshot|cache)_test$'])
    state['candidate_binary_sha256']=hashlib.file_digest((r/'build/strata').open('rb'),'sha256').hexdigest()
    for candidate, modes in [(True,['disk','ram','ram-fallback']),(False,['ram','ram-fallback'])]:
        cfg=json.loads((r/'config.json').read_text())
        cfg['exe']=str(r/('build/strata' if candidate else 'strata-baseline'))
        c=r/('candidate-config.json' if candidate else 'baseline-config.json')
        c.write_text(json.dumps(cfg,indent=2))
        for mode in modes:
            name=('candidate-' if candidate else 'baseline-')+mode
            args=[sys.executable,str(r/'probe_extended.py'),'--source',str(r/'source'),'--config',str(c),
                  '--output',str(r/name),'--mtp','/home/dflanag3/Strata-data/mtp/rt','--cache-mode',mode]
            if not candidate:args+=['--only-mtp']
            run(name,args)
            state['runs'].append({'name':name,**json.loads((r/name/'complete.json').read_text())})
    state.update(phase='complete',finished=time.time())
except BaseException:
    state.update(phase='failed',error=traceback.format_exc())
finally:
    (r/'matrix-status.json').write_text(json.dumps(state,indent=2))
