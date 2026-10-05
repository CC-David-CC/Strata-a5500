"""Concurrent decode scaling. No new serial benchmarks; shared immutable weights.

One process per placement/policy, fixed slot capacity across N, FP16 KV, 8K+512.
No decoding inside another request's prompt chunks: isolate simultaneous decode.
"""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import random
import subprocess
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('STRATA_BENCH_OUTPUT', 'concurrency-results')).resolve()
ROOT.mkdir(exist_ok=True)
ENGINE_ROOT = Path(os.environ.get('STRATA_BENCH_ENGINE_ROOT', BASE.parents[1])).resolve()
PREVIOUS = BASE / 'plans'
SOURCE = Path(os.environ.get('STRATA_BENCH_SOURCE', ENGINE_ROOT)).resolve()
sys.path[:0] = [str(SOURCE), str(SOURCE / 'tools'), str(BASE)]
os.environ['STRATA_PARALLEL_SOLO'] = '0'
from client_helpers import TracedEngine
from serve.frontend import ChatTemplate
from strata_tokenizer import Tokenizer

ap = argparse.ArgumentParser()
ap.add_argument('--model', required=True)
ap.add_argument('--policy', choices=['mtp', 'nomtp'], default='mtp')
ap.add_argument('--placement', choices=['full', 'half-ram', 'half-mmap', 'half-direct', 'q8-base', 'q8-ram', 'q8-mmap'], default='full')
ap.add_argument('--counts', default='2,3,4,6,8')
ap.add_argument('--capacity', type=int, default=8)
ap.add_argument('--label', required=True)
ap.add_argument('--repeat-best', action='store_true')
ap.add_argument('--input', type=int, default=8192)
ap.add_argument('--output', type=int, default=512)
ap.add_argument('--cache-gib', type=float)
ap.add_argument('--ple-mode', choices=['ram','mmap','direct'])
ap.add_argument('--repeat-count', type=int, default=0)
ap.add_argument('--shuffle', type=int, default=0)
ap.add_argument('--waves', type=int, choices=[0,1], default=1)
ap.add_argument('--stream-target', type=float, default=7.0)
ap.add_argument('--stream-floor', type=float, default=4.0)
ap.add_argument('--start-at-requested', action='store_true')
opt = ap.parse_args()
COUNTS = [int(n) for n in opt.counts.split(',')]
if COUNTS[0] > 2 and not opt.start_at_requested:
    COUNTS.insert(0, 2)  # establish the per-stream floor before testing a larger batch
assert min(COUNTS) >= 1 and max(COUNTS) <= opt.capacity
assert opt.capacity<=64
if opt.shuffle:
    import random
    random.Random(opt.shuffle).shuffle(COUNTS)
if opt.repeat_count:
    original=list(COUNTS)
    for rep in range(opt.repeat_count):
        block=list(original)
        random.Random(opt.shuffle+rep+1).shuffle(block)
        COUNTS.extend(block)
OUT = ROOT / 'scaling' / opt.label
OUT.mkdir(parents=True, exist_ok=False)
report = dict(started_unix=time.time(), completed=False, runs=[], options=vars(opt),
              source_commit=subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip(),
              harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              protocol='Concurrent requests; actual input and committed output lengths recorded in options; greedy, thinking off, FP16 KV. Shared weights, private request state. Fixed slot capacity/cache within each case. Prompt cache and decode during prefill off. Solo baseline uses T4 with MTP or target-only without; batched MTP proposes one token/slot and verifies up to four slots/eight rows; non-MTP verifies up to eight slots. Larger logical populations rotate groups. Ngram speculation off.',
              caveats=['Screening results; ordering, cache warmth and graph capture affect timing.',
                       'mmap allows OS page cache; it is not a guaranteed physical disk read for each row.',
                       'Current batch step applies pending swaps but does not start asynchronous adaptation rounds. Placement is static during grouped decode; flags do not prove adaptation is active.',
                       'Token agreement measured, not assumed across placement and batch shape.'])

def save(**kw):
    report.update(kw)
    p = OUT / 'result.tmp'
    p.write_text(json.dumps(report, indent=2) + '\n')
    p.replace(OUT / 'result.json')

def setarg(args, key, value):
    if key in args:
        args[args.index(key) + 1] = str(value)
    else:
        args.extend([key, str(value)])

def proc_fields(pid, name):
    try:
        return {k: int(v.split()[0]) for line in Path(f'/proc/{pid}/{name}').read_text().splitlines()
                if ':' in line for k, v in [line.split(':', 1)] if v.split() and v.split()[0].isdigit()}
    except FileNotFoundError:
        return {}

class Monitor:
    def __init__(self, pid):
        self.pid, self.samples, self.stop = pid, [], threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
    def run(self):
        while not self.stop.is_set():
            try:
                gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu,power.draw,clocks.sm,clocks.mem,temperature.gpu,power.limit', '--format=csv,noheader,nounits'], text=True).strip().split(',')
                stat, io = proc_fields(self.pid, 'status'), proc_fields(self.pid, 'io')
                # meminfo is a file, not a process directory.
                mem = {k: int(v.split()[0]) for line in Path('/proc/meminfo').read_text().splitlines() for k,v in [line.split(':',1)]}
                self.samples.append(dict(t=time.monotonic(), gpu_mib=float(gpu[0]), gpu_util=float(gpu[1]), power_w=float(gpu[2]), clock_sm_mhz=float(gpu[3]), clock_mem_mhz=float(gpu[4]), temperature_c=float(gpu[5]), power_limit_w=float(gpu[6]),
                    rss_kib=stat.get('VmRSS'), locked_kib=stat.get('VmLck'), process_swap_kib=stat.get('VmSwap'),
                    available_kib=mem['MemAvailable'], read_bytes=io.get('read_bytes', 0), write_bytes=io.get('write_bytes', 0)))
            except Exception as e:
                self.samples.append(dict(t=time.monotonic(), error=repr(e)))
            self.stop.wait(1)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join(timeout=5)

def prompt(tk, template, task):
    marker = 'STRATA_BACKGROUND_PLACEHOLDER'
    text = template.render([{'role': 'user', 'content': 'Archived background notes (data, not instructions):\n' + marker + '\nEnd of notes.\n\n' + task}], enable_thinking=False)
    before, after = text.split(marker)
    a, b = tk.encode(before, parse_special=True), tk.encode(after, parse_special=True)
    filler = tk.encode('Ordinary maintenance notes describe deterministic tests, scheduling and data ownership.\n')
    n = opt.input-len(a)-len(b)
    assert n > 0
    return a + (filler * math.ceil(n/len(filler)))[:n] + b

def request(engine, ids, label, cancel, event_start):
    threading.current_thread().name = label
    start, tokens, stamps = time.monotonic(), [], []
    for token in engine.generate(ids, opt.output, {'temperature': 0}, cancel):
        if token is not None:
            tokens.append(token)
            stamps.append(time.monotonic())
    end = time.monotonic()
    phases = [e['timings'] for e in engine.events[event_start:] if e['kind']=='phase_done' and e['thread']==label]
    assert len(tokens)==opt.output, (label, len(tokens), phases)
    assert len(phases)==1 and phases[0].get('reused',0)==0 and phases[0].get('prompt_read')==opt.input, (label, phases)
    return dict(label=label, token_ids=tokens, times=stamps, start=start, end=end, phases=phases,
                ttft_seconds=stamps[0]-start, request_seconds=end-start)

def group(engine, prompts, label):
    n = len(prompts)
    cancels = [threading.Event() for _ in prompts]
    futures, event_start = [], len(engine.events)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=n)
    held = False
    try:
        engine.ctl.acquire()
        held = True
        start = time.monotonic()
        for i, ids in enumerate(prompts):
            futures.append(pool.submit(request, engine, ids, f'{label}-client-{i}', cancels[i], event_start))
        deadline = time.monotonic()+30
        while True:
            with engine.slot_cv:
                waiting = engine.waiting
            if waiting==n:
                break
            if time.monotonic()>deadline:
                raise TimeoutError(('admission barrier', waiting, n))
            time.sleep(.001)
        engine.ctl.release()
        held = False
        requests = [f.result(timeout=max(1800,opt.input/8192*n*120+opt.output/4)) for f in futures]
        end = time.monotonic()
    except BaseException:
        for c in cancels:
            c.set()
        if engine.proc.poll() is None:
            engine.proc.terminate()
        raise
    finally:
        if held:
            engine.ctl.release()
        pool.shutdown(wait=True, cancel_futures=True)
    def interval(index):
        first = max(r['times'][index] for r in requests)
        last = min(r['times'][-1] for r in requests)
        assert last>first, ('no simultaneous decode interval', n, index)
        counts = [sum(first<=t<=last for t in r['times']) for r in requests]
        return dict(seconds=last-first, tokens_per_request=counts, committed_tok_s=sum(counts)/(last-first))
    overlap, steady = interval(0), interval(63)
    assert min(steady['tokens_per_request'])>=200, ('too little fully concurrent decode', steady)
    return dict(n=n, requests=requests, seconds=end-start, aggregate_effective_tok_s=n*opt.output/(end-start),
                overlap=overlap, steady=steady, prompt_tokens_read=sum(p['prompt_read'] for r in requests for p in r['phases']))

engine = None
try:
    save(phase='waiting_for_gpu_lock')
    lock = Path(os.environ.get('STRATA_BENCH_LOCK', str(ROOT / '.benchmark.lock'))).open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX)
    busy = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'], text=True).strip()
    if busy:
        raise RuntimeError('GPU is busy: '+busy)
    planpath = PREVIOUS/(opt.model+'-plan.json')
    plan = json.loads(planpath.read_text())
    for key in ('pack', 'native'):
        plan[key] = os.path.expandvars(plan[key])
    plan['common_args'] = [os.path.expandvars(a) for a in plan['common_args']]
    if any('${' in a for a in plan['common_args']):
        raise ValueError('Set PACK, NATIVE, MTP and PROFILE as documented')
    args = list(plan['common_args'])
    setarg(args,'--prompt-cache',0)
    for k,v in [('--batch',opt.capacity),('--max-context',math.ceil((opt.input+opt.output+8)/8192)*8192),('--mtp-max-t',4 if opt.policy=='mtp' else 1),('--adapt-every',0)]:
        setarg(args,k,v)
    total_cache = int(args[args.index('--expert-cache')+1])
    if opt.placement.startswith('half-'):
        setarg(args,'--expert-cache',total_cache//2)
        setarg(args,'--resident-budget-gib',64)
        setarg(args,'--ple-io',opt.placement.split('-')[1])
    elif opt.placement.startswith('q8-'):
        setarg(args,'--expert-cache',15472 if opt.placement=='q8-base' else 12288)
        setarg(args,'--resident-budget-gib',64)
        setarg(args,'--ple-io','mmap' if opt.placement=='q8-mmap' else 'ram')
    assert opt.model!='q8' or opt.placement.startswith('q8-')
    requested_full = opt.placement=='full'
    if opt.cache_gib is not None:
        rows=[l.split() for l in (Path(plan['pack'])/'native_experts.txt').read_text().splitlines() if l and not l.startswith('#')]
        header=(Path(plan['pack'])/'native_experts.txt').read_text().splitlines()[0]
        expert_count=int(re.search(r'n_expert (\d+)',header).group(1))
        sizes=[int(l[4]) for l in rows]
        model_bytes=sum(sizes)*expert_count
        requested_full=opt.cache_gib*2**30>=model_bytes
        slots=len(rows)*expert_count if requested_full else int(opt.cache_gib*2**30//max(sizes))
        setarg(args,'--expert-cache',slots)
        total_cache=len(rows)*expert_count
        if not requested_full:setarg(args,'--resident-budget-gib',96)
        report['expert_layout']=dict(layers=len(rows),experts_per_layer=expert_count,total_bytes=model_bytes,max_blob_bytes=max(sizes),requested_cache_gib=opt.cache_gib,requested_slots=slots,full=requested_full)
    if opt.ple_mode:setarg(args,'--ple-io',opt.ple_mode)
    if '--resident-budget-gib' in args and requested_full:
        k=args.index('--resident-budget-gib');del args[k:k+2]
    report['requested_full']=requested_full
    # The source currently advances async adaptation in solo decode, not grouped decode.
    # Static profile-ranked cache is deliberately explicit instead of claiming inactive flags help.
    env = {k:v for k,v in os.environ.items() if not k.startswith('STRATA_') and k!='MULTI_CONCURRENCY'}
    env.update(plan['environment'])
    env.update(STRATA_BATCH_WAVES=str(opt.waves), STRATA_DF_PDL=os.environ.get('STRATA_BENCH_PDL', '0'), STRATA_DF_BRANCH=os.environ.get('STRATA_BENCH_GRAPH_BRANCHES', '0'), STRATA_PARALLEL_SOLO='0', STRATA_BATCH_DECODE_SHARE='0', STRATA_VERIFY_DEVICE_PLAN='0')
    if opt.policy=='mtp':
        env['MULTI_CONCURRENCY']='TRUE'
    exe = os.environ.get('STRATA_BENCH_EXE', str(ENGINE_ROOT/'build/strata'))
    report.update(args=args, environment={k:v for k,v in env.items() if k.startswith('STRATA_') or k=='MULTI_CONCURRENCY'},
                  engine_sha256=hashlib.file_digest(open(exe,'rb'),'sha256').hexdigest(),
                  gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,power.limit,memory.total','--format=csv'],text=True))
    tk, template = Tokenizer.from_gguf(plan['native']), ChatTemplate(Path(plan['pack'])/'tokenizer/chat_template.jinja')
    tasks = [plan['tasks']['code'], 'Write a complete Python module implementing a robust INI configuration parser with validation, default values, error messages and deterministic tests using unittest. Include the full code and tests. Do not discuss the archived notes.']
    topics = ['LRU cache with TTL', 'directed graph topological sort and cycle detection', 'streaming CSV validator', 'retry queue with exponential backoff', 'bounded producer consumer queue', 'calendar interval merge and conflicts', 'stable heap with decrease key', 'transactional key value store', 'binary search tree iterator', 'rate limiter', 'configuration schema validator', 'file checksum catalogue', 'ordered event replay', 'URL path router', 'immutable prefix tree', 'worker scheduler with priorities', 'structured log parser', 'rolling statistics calculator', 'dependency graph planner', 'byte ring buffer', 'monotonic stopwatch', 'JSON pointer resolver', 'incremental UTF8 decoder', 'range set with subtraction', 'depth first graph walker', 'unique identifier allocator', 'directory inventory comparer', 'fixed size object pool', 'cancellation token registry', 'timestamp index']
    tasks += ['Write a complete Python module implementing '+t+' with validation, explicit ownership, error handling and deterministic unittest tests. Include the full code and tests. Do not discuss the archived notes.' for t in topics]
    while len(tasks)<opt.capacity:
        j=len(tasks)
        tasks.append(tasks[j%32]+' Use descriptive symbols for request variant '+str(j+1)+'.')
    prompts = [prompt(tk,template,t) for t in tasks[:opt.capacity]]
    previous_inputs = PREVIOUS/'parallel2-fixed-enhanced'/(opt.model+'-inputs.json')
    if opt.input==8192 and previous_inputs.exists():
        assert prompts[:2]==json.loads(previous_inputs.read_text()), 'A/B prompt compatibility'
    (OUT/'inputs.json').write_text(json.dumps(prompts)+'\n')
    report['input_sha256'] = hashlib.sha256((OUT/'inputs.json').read_bytes()).hexdigest()
    log = OUT/'engine.log'
    save(phase='loading')
    startup = time.monotonic()
    engine = TracedEngine(exe,args,str(SOURCE),str(log),env)
    report.update(startup_seconds=time.monotonic()-startup,engine_info=engine.info)
    assert engine.batch==opt.capacity, ('capacity changed', engine.info)
    loaded = log.read_text()
    report['placement_log'] = [l for l in loaded.splitlines() if any(x in l for x in ['PLE table','resident RAM mode','resident cache complement','RAM budget','token graph hit path','slot sessions','expert cache'])]
    if args[args.index('--ple-io')+1]=='ram':
        assert 'PLE table locked in RAM' in loaded
    if requested_full:
        assert f'token graph hit path: {total_cache} resident experts' in loaded
    else:
        assert 'resident RAM mode:' in loaded and 'cannot be kept' not in loaded, 'Resident complement did not initialize'
    if opt.policy=='mtp':
        assert loaded.count('shared draft weights')==opt.capacity
    sequence = list(COUNTS)
    reference_tokens = {}
    i = 0
    while i<len(sequence):
        n = sequence[i]
        earlier = [r for r in report['runs'] if 1<r['n'] < n]
        if earlier:
            last = max(earlier,key=lambda r:r['n'])
            per_stream = [c/last['steady']['seconds'] for c in last['steady']['tokens_per_request']]
            projected_slowest = min(per_stream)*last['n']/n
            # A wider physical window can still improve aggregate throughput.
            # Allow a bounded probe within the user's 4-7 range, with 10% margin
            # over the hard floor. Once rows are full, more slots only time-share.
            physical_slots = 4 if opt.policy=='mtp' else 8
            required = opt.stream_floor*1.1
            if projected_slowest < required:
                report.setdefault('skipped_counts',[]).append(dict(n=n,reason='projected slowest stream below advance threshold',projected_tok_s=projected_slowest,advance_threshold=required,target=opt.stream_target,hard_floor=opt.stream_floor,from_n=last['n']))
                print('SKIP',opt.model,opt.placement,opt.policy,n,'projected_stream',round(projected_slowest,2),flush=True)
                i += 1
                if i==len(COUNTS) and opt.repeat_best and report['runs']:
                    eligible=[r for r in report['runs'] if r.get('meets_stream_target',False)]
                    best=sorted(eligible,key=lambda r:r['aggregate_effective_tok_s'],reverse=True)[:2]
                    sequence.extend(r['n'] for r in reversed(best))
                save()
                continue
        label = f'n{n}-r{sum(r["n"]==n for r in report["runs"])}'
        save(phase='running-'+label)
        start_log = log.stat().st_size
        before_io = proc_fields(engine.proc.pid,'io')
        with Monitor(engine.proc.pid) as mon:
            row = group(engine,prompts[:n],label)
        row.update(label=label,samples=mon.samples)
        row['per_stream_steady_tok_s']=[c/row['steady']['seconds'] for c in row['steady']['tokens_per_request']]
        row['meets_stream_target']=min(row['per_stream_steady_tok_s'])>=opt.stream_target
        row['meets_stream_floor']=min(row['per_stream_steady_tok_s'])>=opt.stream_floor
        after_io = proc_fields(engine.proc.pid,'io')
        row['process_disk_read_bytes'] = after_io.get('read_bytes',0)-before_io.get('read_bytes',0)
        delta = log.read_bytes()[start_log:].decode(errors='replace')
        (OUT/(label+'.log')).write_text(delta)
        counts = re.findall(r'strata batch MTP: slot (\d+) proposed=(\d+) accepted=(\d+) generated=(\d+) finish=(\S+)',delta)
        row['slot_mtp'] = [dict(slot=int(b),proposed=int(p),accepted=int(a),generated=int(g),finish=f) for b,p,a,g,f in counts]
        if opt.policy=='mtp' and n>1:
            assert len(counts)==n and all(c['generated']==opt.output and c['generated']==1+c['proposed']+c['accepted'] and c['finish']=='length' for c in row['slot_mtp']), counts
        else:
            assert not counts
        row['is_solo_baseline']=(n==1)
        row['batch_summary'] = [l for l in delta.splitlines() if l.startswith('strata batch:') and 'ms/window' in l]
        row['parity_to_first_seen'] = []
        for j,req in enumerate(row['requests']):
            ref = reference_tokens.setdefault(j,req['token_ids'])
            first = next((k for k,(a,b) in enumerate(zip(ref,req['token_ids'])) if a!=b),None)
            row['parity_to_first_seen'].append(dict(request=j,identical=first is None,first_difference=first))
        report['runs'].append(row)
        print('DONE',opt.model,opt.placement,opt.policy,label,'stream',round(row['overlap']['committed_tok_s'],2),'steady',round(row['steady']['committed_tok_s'],2),'effective',round(row['aggregate_effective_tok_s'],2),'read_MiB',round(row['process_disk_read_bytes']/2**20,1),flush=True)
        save()
        i += 1
        if not row['meets_stream_floor']:
            report['stopped_for_stream_floor']=dict(n=n,slowest_tok_s=min(row['per_stream_steady_tok_s']),floor=opt.stream_floor)
            break
        if i==len(COUNTS) and opt.repeat_best:
            eligible=[r for r in report['runs'] if r['meets_stream_target']]
            best = sorted(eligible,key=lambda r:r['aggregate_effective_tok_s'],reverse=True)[:2]
            sequence.extend(r['n'] for r in reversed(best))
    engine.close()
    (OUT/'events.json').write_text(json.dumps(engine.events,indent=2)+'\n')
    engine = None
    save(phase='complete',completed=True,finished_unix=time.time())
except BaseException as e:
    if engine:
        engine.close()
        (OUT/'events.json').write_text(json.dumps(engine.events,indent=2)+'\n')
    save(phase='failed',error=repr(e),finished_unix=time.time())
    raise
