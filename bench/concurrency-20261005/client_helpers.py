"""Client timing and tracing helpers copied from the completed staggered screen."""
import concurrent.futures
import threading
import time
from serve.server import StrataEngine

class TracedEngine(StrataEngine):
    def __init__(self, *args, **kwargs):
        self.events = []
        self.event_lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def event(self, kind, **data):
        with self.event_lock:
            self.events.append(dict(kind=kind, monotonic=time.monotonic(),
                                    thread=threading.current_thread().name, **data))

    def _send(self, text):
        parts = text.split()
        if parts and parts[0] in ('GEN', 'BGEN', 'GENI', 'BGENI'):
            summary = ' '.join(parts[:-1])
            count = len(parts[-1].split(','))
        else:
            summary, count = text[:160], None
        self.event('send', command=summary, prompt_tokens=count)
        return super()._send(text)

    def _parse_done(self, line):
        super()._parse_done(line)
        self.event('phase_done', timings=dict(self.last))

    def _pump(self):
        proc, lines, slots = self.proc, self.lines, self.slot_q
        with open(self.log_path + '.protocol', 'a', buffering=1) as trace:
            for line in proc.stdout:
                trace.write(line)
                if line.startswith(('DONE', 'BADM ', 'BDONE ', 'REUSED ', 'RESUME ', 'ERR')):
                    self.event('received', line=line.strip())
                if line.startswith(('BT ', 'BDONE ')) and slots:
                    try:
                        slots[int(line.split()[1])].put(line)
                        continue
                    except (IndexError, ValueError):
                        pass
                lines.put(line)
        if self.proc is proc:
            self.ended = True
        lines.put(None)
        for q in slots:
            q.put(None)

def request(engine, ids, label, cancel, first=None):
    threading.current_thread().name = label
    start = time.monotonic()
    tokens, stamps = [], []
    engine.event('client_start', label=label)
    try:
        for token in engine.generate(ids, 512, {'temperature': 0}, cancel):
            if token is not None:
                tokens.append(token)
                stamps.append(time.monotonic())
                if len(tokens) == 1 and first:
                    first.set()
    finally:
        engine.event('client_end', label=label, tokens=len(tokens))
    end = time.monotonic()
    assert len(tokens) == 512, (label, len(tokens), engine.last)
    phases = [e['timings'] for e in engine.events
              if e['kind'] == 'phase_done' and e['thread'] == label]
    return dict(label=label, input_tokens=len(ids), output_tokens=len(tokens), token_ids=tokens,
                token_times_monotonic=stamps, start_monotonic=start, end_monotonic=end,
                request_seconds=end-start, ttft_seconds=stamps[0]-start,
                post_first_token_tok_s=511/(stamps[-1]-stamps[0]),
                effective_tok_s=512/(end-start), engine_final_phase=dict(engine.last), phases=phases)

def run_pair(engine, prompts, policy):
    cancels = [threading.Event(), threading.Event()]
    first = threading.Event()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    futures = []
    barrier_held = False
    try:
        if policy == 'simultaneous':
            engine.ctl.acquire()
            barrier_held = True
        pair_start = time.monotonic()
        futures.append(pool.submit(request, engine, prompts[0], 'client-A', cancels[0], first))
        if policy == 'staggered':
            deadline = time.monotonic() + 120
            while not first.wait(0.05):
                if futures[0].done():
                    futures[0].result()
                    raise RuntimeError('A ended without emitting its first token')
                if time.monotonic() > deadline:
                    raise TimeoutError('A did not emit its first token')
        futures.append(pool.submit(request, engine, prompts[1], 'client-B', cancels[1]))
        if barrier_held:
            deadline = time.monotonic() + 15
            while True:
                with engine.slot_cv:
                    waiting = engine.waiting
                if waiting == 2:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('Both clients did not reach admission barrier')
                time.sleep(0.001)
            engine.ctl.release()
            barrier_held = False
        pair = [f.result(timeout=180) for f in futures]
        pair_end = time.monotonic()
    except BaseException:
        for c in cancels:
            c.set()
        if engine.proc.poll() is None:
            engine.proc.terminate()
        raise
    finally:
        if barrier_held:
            engine.ctl.release()
        pool.shutdown(wait=True, cancel_futures=True)
    a, b = pair
    overlap_start = max(r['token_times_monotonic'][0] for r in pair)
    overlap_end = min(r['token_times_monotonic'][-1] for r in pair)
    assert overlap_end > overlap_start, 'No concurrent output interval'
    during = [sum(overlap_start <= t <= overlap_end for t in r['token_times_monotonic']) for r in pair]
    assert min(during) > 0
    # Each independent 8K prompt must really be read. Only A's promoted prefix may be reused.
    assert a['phases'][0].get('reused') == 0, a['phases']
    assert b['phases'][0].get('reused') == 0, b['phases']
    assert b['phases'][0]['prompt_read'] == 8192, b['phases']
    if policy == 'staggered':
        assert b['start_monotonic'] >= a['token_times_monotonic'][0]
        assert len(a['phases']) >= 2, 'A did not promote from solo to a batch slot'
        assert a['phases'][1]['reused'] >= 8191, a['phases']
    else:
        assert len(a['phases']) == len(b['phases']) == 1
    return dict(requests=pair, pair_seconds=pair_end-pair_start,
                aggregate_effective_tok_s=1024/(pair_end-pair_start),
                arrival_delay_seconds=b['start_monotonic']-a['start_monotonic'],
                global_completion_seconds=[r['end_monotonic']-pair_start for r in pair],
                overlap_seconds=overlap_end-overlap_start,
                overlap_tokens_per_request=during,
                overlap_committed_tok_s=sum(during)/(overlap_end-overlap_start),
                prompt_tokens_read=sum(p.get('prompt_read', 0) for r in pair for p in r['phases']))
