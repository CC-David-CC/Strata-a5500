import json, re
from pathlib import Path
r=Path(__file__).resolve().parent
def tokens(p):
    # StrataEngine also yields None heartbeats; compare model tokens, not polling timing.
    return [v for v in json.loads(p.read_text()) if type(v) is int]
report={'arms':[],'parity':[],'restore_parity':[]}
for run in sorted(r.glob('*-*/rows.json')):
    if not run.parent.name.startswith(('candidate-','baseline-')):continue
    rows=json.loads(run.read_text())
    for arm in sorted({v['arm'] for v in rows}):
        a=[v for v in rows if v['arm']==arm]
        last=next((v for v in a if v['label']=='return-new-suffix'),None)
        first=a[0]
        d={'run':run.parent.name,'arm':arm,'generations':len(a),'cold_prompt_ms':first['engine']['prompt_ms']}
        if last:d.update(reused=last['engine']['reused'],return_prompt_ms=last['engine']['prompt_ms'],return_total_s=last['total_s'])
        log=(run.parent/arm/'engine.log').read_text()
        d['prefix_saves']=re.findall(r'prefix-saved the (\d+)-token root',log)
        d['positive_cleanup_events']=len(re.findall(r'[1-9]\d* older cop(?:y|ies) dropped',log))
        d['failure']=(run.parent/arm/'failure.json').exists()
        report['arms'].append(d)
        auto=run.parent/arm/'return-new-suffix-events.json'
        for label in ['explicit-restore-control','restart-return']:
            control=run.parent/arm/(label+'-events.json')
            if auto.exists() and control.exists():
                report['restore_parity'].append({'run':run.parent.name,'arm':arm,'control':label,
                    'equal':tokens(auto)==tokens(control)})
for base in r.glob('baseline-*/*/*-events.json'):
    candidate=r/('candidate-'+base.parent.parent.name.removeprefix('baseline-'))/base.parent.name/base.name
    if not candidate.exists():continue
    old=tokens(base); new=tokens(candidate)
    report['parity'].append({'run':base.parent.parent.name,'arm':base.parent.name,'request':base.name,
                            'equal':old==new,'baseline_tokens':len(old),'candidate_tokens':len(new)})
(r/'summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'arms':report['arms'],'parity_equal':sum(x['equal'] for x in report['parity']),
                  'parity_total':len(report['parity']),'mismatches':[x for x in report['parity'] if not x['equal']],
                  'restore_parity':report['restore_parity']},indent=2))
