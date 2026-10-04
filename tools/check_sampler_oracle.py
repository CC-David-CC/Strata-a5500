"""Independent full-row FP64 oracle for the first six native HTTP sampler cases.

Input is six LPRAW1 rows from STRATA_LOGPROBS_RAW, gzip compressed. No model runs.
"""
import argparse, gzip, json, math, pathlib, struct

def probabilities(values):
    m=max(values.values()); weights={k:math.exp(v-m) for k,v in values.items()}
    z=math.fsum(weights.values()); return {k:w/z for k,w in weights.items()}
def entropy(p): return -math.fsum(v*math.log(v) for v in p.values() if v)
def check(path, receipts):
    results=[]
    with gzip.open(path,'rb') as f:
        for case in receipts['cases'][:6]:
            header=f.readline().decode().split(); assert header[0]=='LPRAW1'
            nv=int(header[-1]); selected=int(header[-3]); assert int(header[3])==0 and int(header[4])==1
            raw=struct.unpack('<'+'f'*nv,f.read(nv*4)); assert f.read(1)==b'\n'
            values=dict(enumerate(raw)); sampler=case['request']['strata_sampler']
            entry=case['response']['choices'][0]['logprobs']['content'][0]; receipt=entry['strata_sampling']
            assert receipt['id']==selected
            m=max(raw); z=m+math.log(math.fsum(math.exp(x-m) for x in raw))
            raw_error=abs(raw[selected]-z-entry['logprob']); errors=[]
            for op,stage in zip(['grammar']+sampler['chain'],receipt['stages']):
                if op=='temperature': values={k:v/sampler['temperature'] for k,v in values.items()}
                if op=='top_k' and sampler['top_k']:
                    values=dict(sorted(values.items(),key=lambda kv:(-kv[1],kv[0]))[:sampler['top_k']])
                if op=='min_p' and sampler['min_p']:
                    cut=max(values.values())+math.log(sampler['min_p']);values={k:v for k,v in values.items() if v>=cut}
                if op=='top_n_sigma' and sampler['top_n_sigma']:
                    mean=math.fsum(values.values())/len(values)
                    std=math.sqrt(math.fsum((v-mean)**2 for v in values.values())/len(values))
                    cut=max(values.values())-sampler['top_n_sigma']*std
                    values={k:v for k,v in values.items() if v>=cut}
                if op=='xtc':
                    assert sampler['xtc_probability']==1, 'oracle fixture uses a deterministic gate'
                    probs=probabilities(values)
                    over=sorted([k for k,p in probs.items() if p>=sampler['xtc_threshold']],key=lambda k:(-values[k],k))
                    for k in over[:-1]: values.pop(k)
                probs=probabilities(values)
                assert len(values)==stage['support'],(case['case'],op,len(values),stage['support'])
                errors.append(abs(entropy(probs)-stage['entropy']))
            final_error=abs(probs[selected]-receipt['probability'])
            top_error=max(abs(probs[v['id']]-v['probability']) for v in receipt['top'])
            assert max([raw_error,final_error,top_error,*errors]) < 1e-9
            results.append(dict(case=case['case'],vocabulary=nv,support=len(values),selected=selected,
                raw_logprob_error=raw_error,selected_probability_error=final_error,top_probability_error=top_error,
                maximum_entropy_error=max(errors),selection_ms=receipt['selection_ms']))
    return dict(provenance='independent FP64 oracle over native captured FP32 rows',cases=results,tolerance=1e-9)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('rows');p.add_argument('receipts');p.add_argument('--output')
    a=p.parse_args();result=check(a.rows,json.loads(pathlib.Path(a.receipts).read_text()))
    text=json.dumps(result,indent=2)
    if a.output:pathlib.Path(a.output).write_text(text,encoding='utf-8')
    print(text)
if __name__=='__main__':main()
