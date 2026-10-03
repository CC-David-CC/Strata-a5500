#!/usr/bin/env python3
"""GPU arithmetic, memory, output and committed-state gates for wide windows."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',type=Path,required=True)
    ap.add_argument('--prompt',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    opt=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    cfg=json.loads(opt.config.read_text())
    build=Path(cfg['exe']).parent
    opt.output.mkdir(parents=True,exist_ok=False)
    status={'micro':[],'state':[],'complete':False}
    def save():
        (opt.output/'gate.json').write_text(json.dumps(status,indent=2))
    def run(label,args):
        with (opt.output/(label+'.log')).open('w') as f:
            subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT,check=True)
    save()
    env=dict(os.environ,**cfg.get('env',{}))
    os.environ.update(env)
    for name in ['mmvq_multi_parity','wide_bf16_parity','iq_multi_parity','s2_expert_grouped_parity','gr_parity']:
        args=[build/name]
        if name in ('gr_parity','s2_expert_grouped_parity'):args.append('--selftest')
        run(name,args)
        run(name+'-memcheck',['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck',
            '--error-exitcode','99',*args])
        status['micro'].append({'name':name,'parity':True,'memcheck':True});save()
    # Shared staging and warp compaction have changed; check their barriers too.
    for tool in ('racecheck','synccheck'):
        run('grouped-'+tool,['/usr/local/cuda/bin/compute-sanitizer','--tool',tool,
            '--error-exitcode','99',build/'s2_expert_grouped_parity','--selftest'])
    def state(label,width,caps,depth=None):
        args=[sys.executable,root/'tools/bench_state_boundaries.py','--config',opt.config,
              '--prompt',opt.prompt,'--output',opt.output/label,'--verify-window',width,
              '--mtp-window',width,'--caps',*caps]
        if depth is not None:args+=['--oracle-sweep','--reject-depth',depth]
        run(label,args)
        result=json.loads((opt.output/label/'result.json').read_text())
        passed=all(x['tokens_match'] and x['serial_consumed_ok'] and x['mtp_consumed_ok']
                   and not x['different_state_fields'] for x in result['comparison'])
        status['state'].append({'label':label,'width':width,'depth':depth,
                                'passed':passed,'comparison':result['comparison']});save()
        if not passed:raise RuntimeError('Committed-state mismatch: '+label)
    try:
        for width in (8,12,16,18,24):
            state('real-t'+str(width),width,[width-1,width,width+1,2*width+3])
        # Full acceptance plus every possible draft rejection depth at capacity.
        for depth in [-1,*range(23)]:
            state('oracle-t24-reject'+str(depth),24,[51],depth)
        # Odd/tail window layouts need checks as well as the maximum allocation.
        for width in (12,16,18):
            state('oracle-t'+str(width),width,[2*width+3],width-2)
        status['complete']=True
    finally:save()


if __name__=='__main__':main()
