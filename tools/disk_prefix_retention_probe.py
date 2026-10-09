"""Generic native-engine reproduction; contains no private profile or wrapper.

python public_cache_probe.py --source STRATA --config CONFIG --output RESULTS
Runs disk-only shared-prefix switching, unpinned/pinned, without/with MTP.
The supplied config selects the model, backend, and optional MTP runtime.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--mtp', type=Path)
    ap.add_argument('--resume', action='store_true')
    a = ap.parse_args()
    sys.path[:0] = [str(a.source), str(a.source/'tools')]
    from serve.server import StrataEngine, engine_args, child_env
    from serve.frontend import ChatTemplate
    import strata_tokenizer as ST
    cfg = json.loads(a.config.read_text()); cfg.pop('api_key', None)
    tp = Path(cfg['tokenizer']); vocab = json.loads((tp/'vocab.json').read_text())
    tokens = [None]*len(vocab)
    for token, index in vocab.items(): tokens[index] = token
    tok = ST.Tokenizer(tokens, (tp/'merges.txt').read_text().split('\n'), json.loads((tp/'token_type.json').read_text()))
    template = ChatTemplate(tp/'chat_template.jinja')
    def encode(text, closed=False):
        messages=[dict(role='user', content=text)]
        if closed: messages.append(dict(role='assistant', content='I will use this reference.'))
        return tok.encode(template.render(messages, add_generation_prompt=not closed, enable_thinking=False), parse_special=True)
    text=''.join(f'Record {i}: Python functions validate input, return values, and preserve explicit state.\n' for i in range(1600))
    lo, hi=0,len(text)
    while lo < hi:
        m=(lo+hi+1)//2
        if len(encode(text[:m],True))<=8192:lo=m
        else:hi=m-1
    prefix=encode(text[:lo],True)
    assert 8188<=len(prefix)<=8192
    rows=[]; a.output.mkdir(parents=True,exist_ok=True)
    if a.resume and (a.output/'rows.json').exists():
        previous=json.loads((a.output/'rows.json').read_text())
        complete={r['arm'] for r in previous if r['label']=='explicit-restore-control'}
        rows=[r for r in previous if r['arm'] in complete]
    for use_mtp in ([False,True] if a.mtp else [False]):
        for pin in [False,True]:
            label=('mtp' if use_mtp else 'off')+('-pinned' if pin else '-unpinned')
            if any(r['arm']==label and r['label']=='explicit-restore-control' for r in rows):continue
            out=a.output/label;out.mkdir(exist_ok=True)
            local=dict(cfg);args=list(cfg['args'])
            for flag in ['--mtp','--conversation-cache-spill-dir','--conversation-cache-disk-mib']:
                if flag in args:
                    i=args.index(flag);del args[i:i+2]
            if '--conversation-cache-disk-only' not in args:args.append('--conversation-cache-disk-only')
            args+=['--conversation-cache-spill-dir',str(out/'kv'),'--conversation-cache-disk-mib','4096']
            if use_mtp:
                args+=['--mtp',str(a.mtp)];args[args.index('--spec')+1]='4'
            local.update(args=args,log=str(out/'engine.log'))
            engine=StrataEngine(local['exe'],engine_args(local),cwd=local['cwd'],log=local['log'],env=child_env(local))
            def gen(name,ids,n=128,with_prefix=False):
                sampling={'temperature':0}
                if pin and with_prefix:sampling['strata_prefix']={'tokens':len(prefix)}
                t=time.perf_counter();list(engine.generate(ids,n,sampling,threading.Event()))
                row=dict(arm=label,label=name,input_tokens=len(ids),prefix_tokens=len(prefix),total_s=time.perf_counter()-t,engine=dict(engine.last))
                rows.append(row);(a.output/'rows.json').write_text(json.dumps(rows,indent=2))
                print(label,name,row['engine'],flush=True)
                return row
            try:
                gen('warm-base',prefix,1,True)
                engine.session_file('save',str(out/'base.session'))
                gen('park-base',encode('Reply READY.'),1)
                for i in range(8):
                    task=('Write a complete Python LRU cache with unit tests.' if i<4 else 'Explain Python parsing, bytecode compilation, and execution.')
                    suffix=task+f' Trial {i}. '+('Discuss concrete examples and make the explanation useful. '*30)
                    suffix=tok.decode(tok.encode(suffix,parse_special=False)[:100])
                    gen('shared-'+str(i),prefix+encode(suffix),128,True)
                gen('switch-away',encode('Summarize the difference between correlation and causation.'),8)
                gen('return-new-suffix',prefix+encode('Give three practical rules for reviewing Python code.'),128,True)
                # Explicit restore remains a control even if automatic reuse misses.
                restored=engine.session_file('restore',str(out/'base.session'))
                (out/'explicit-restore.json').write_text(json.dumps(restored,indent=2))
                gen('explicit-restore-control',prefix+encode('Give three practical rules for reviewing Python code.'),128,True)
            finally:engine.close()
            # Only this probe's disposable snapshots; retain metadata and logs.
            for p in out.rglob('*'):
                if p.is_file() and p.suffix in ('.sess','.session'):
                    assert p.resolve().is_relative_to(a.output.resolve())
                    p.unlink()
    (a.output/'complete.json').write_text(json.dumps({'status':'complete','generations':len(rows)},indent=2))


if __name__=='__main__':main()
