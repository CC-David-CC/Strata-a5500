#!/usr/bin/env python3
"""Bound cached-CPU diversion by free planner slots, without changing the trace."""
from pathlib import Path
import argparse
import json

from analyze_q8_cache_routing import PREFIX, COUNTERS, Replay, analyze


def opportunity(groups, cached, cap=16):
    if cap < 1:
        raise ValueError('Invalid staging capacity')
    gpu = sum(kind == 1 for _, kind, _ in groups)
    if gpu > cap:
        raise ValueError('Baseline exceeds the declared staging capacity')
    cpu = [(expert,count) for expert,kind,count in groups if kind == -1]
    hits = [(expert,count) for expert,count in cpu if expert in cached]
    # Preserve every baseline GPU assignment. Proposed CPU hits are appended
    # in original routing order, only while a staging slot remains.
    selected = hits[:cap-gpu]
    return dict(cpu_groups=len(cpu),cpu_entries=sum(c for _,c in cpu),
        cached_cpu_groups=len(hits),cached_cpu_entries=sum(c for _,c in hits),
        eligible_groups=len(selected),eligible_entries=sum(c for _,c in selected),
        blocked_groups=len(hits)-len(selected),
        blocked_entries=sum(c for _,c in hits[len(selected):]))


def bounded_census(path, cap=16):
    validated=analyze(path,require_exchanges=True)
    sim=Replay(validated['actual_ways'],validated['geometry'][0])
    total={k:0 for k in opportunity([],set(),cap)}
    prior=dict(total);requests=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if PREFIX in line:
            row=json.loads(line.split(PREFIX,1)[1])
            counts=opportunity(row['groups'],set(sim.banks[row['layer']]['tags']),cap)
            for key,value in counts.items():total[key]+=value
            sim.add(row)
        elif COUNTERS.search(line):
            delta={key:total[key]-prior[key] for key in total}
            delta['eligible_fraction_of_cpu_groups']=delta['eligible_groups']/delta['cpu_groups'] if delta['cpu_groups'] else 0
            delta['eligible_fraction_of_cpu_entries']=delta['eligible_entries']/delta['cpu_entries'] if delta['cpu_entries'] else 0
            requests.append(delta);prior=dict(total)
    assert len(requests)==len(validated['requests'])
    for observed,reference in zip(requests,validated['requests']):
        expected=reference['projections'][validated['actual_ways']]
        assert observed['cpu_groups']==expected['cpu_groups']
        assert observed['cached_cpu_groups']==expected['cpu_cached_before_groups']
    return dict(log=str(path),sha256=validated['sha256'],staging_cap=cap,
        actual_cache_ways=validated['actual_ways'],device_counters_exact=validated['device_counters_exact'],
        totals=total,requests=requests,
        interpretation='Independent per-window opportunities on the unchanged measured cache/routing history. '
          'Existing GPU groups retain their slots; cached CPU groups use remaining slots in routing order. '
          'No CPU work was redirected. A sustained policy would change cache ages, arithmetic, routing and '
          'future work; these counts do not simulate that trajectory or predict speed.')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('logs',type=Path,nargs='+')
    ap.add_argument('--output',type=Path,required=True)
    opt=ap.parse_args()
    results=[bounded_census(p) for p in opt.logs]
    opt.output.write_text(json.dumps(dict(traces=results),indent=2)+'\n',encoding='utf-8')
    for r in results:print(r['log'],r['requests'])
