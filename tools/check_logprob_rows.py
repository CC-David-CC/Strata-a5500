"""Independently check optional native LPRAW1 fixtures against JSONL trace scores.

Uses Python's compensated FP64 math.fsum as an independent reference. Example:
  python tools/check_logprob_rows.py evidence/mtp --output evidence/mtp/oracle.json
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys


def read_rows(path):
    with Path(path).open('rb') as stream:
        while header := stream.readline():
            fields=header.decode('ascii').split()
            if len(fields)!=10 or fields[0]!='LPRAW1': raise ValueError('invalid raw fixture header')
            req,window,row,rows,retained,pos,selected,proposed,vocab=map(int,fields[1:])
            if not 0 < vocab <= 300000: raise ValueError('invalid vocabulary size')
            data=stream.read(vocab*4)
            if len(data)!=vocab*4 or stream.read(1)!=b'\n': raise ValueError('truncated raw fixture')
            values=array.array('f')
            values.frombytes(data)
            if sys.byteorder != 'little': values.byteswap()
            yield dict(request=req,window=window,row=row,rows=rows,retained=retained,position=pos,
                       selected=selected,proposed=proposed,values=values)


class logsoftmax:
    def __init__(self, values):
        self.values=values
        self.peak=max(values)
        self.normalizer=math.log(math.fsum(math.exp(v-self.peak) for v in values))

    def __getitem__(self, token):
        return (self.values[token]-self.peak)-self.normalizer


def check(folder):
    records=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    windows={(r['request'],r['window']):r for r in records if r['type']=='verification'}
    maximum=0.0; selected=proposed=rejected_rows=0
    example=None
    for row in read_rows(folder/'raw.bin'):
        reference=logsoftmax(row['values'])
        event=windows[row['request'],row['window']]
        if row['row']<len(event['emitted']):
            token=event['emitted'][row['row']]
            assert token['token_id']==row['selected']
            error=abs(reference[row['selected']]-token['logprob']);maximum=max(maximum,float(error));selected+=1
            assert error<1e-9,error
        if row['proposed']>=0:
            token=event['proposal'][row['row']]
            assert token['token_id']==row['proposed']
            error=abs(reference[row['proposed']]-token['target_logprob']);maximum=max(maximum,float(error));proposed+=1
            assert error<1e-9,error
            if row['row']>=event['accepted_proposals']: rejected_rows+=1
            if example is None and row['selected']!=row['proposed']: example=event
    for event in windows.values():
        assert abs(math.fsum(t['target_logprob'] for t in event['proposal'])-event['target_sequence_logprob'])<1e-10
        for item in event['proposal']:
            if 'draft_probability' in item:
                p=item['draft_probability'];assert 0<=p<=1 and math.isfinite(p)
                if p>0: assert abs(math.log(p)-item['draft_logprob'])<1e-7
    hasher=hashlib.sha256()
    with (folder/'raw.bin').open('rb') as raw:
        while chunk:=raw.read(1024*1024): hasher.update(chunk)
    digest=hasher.hexdigest()
    return dict(selected_rows=selected,proposal_rows=proposed,rejected_or_post_rejection_rows=rejected_rows,
                max_absolute_logprob_error=maximum,raw_sha256=digest,reference='Python math.fsum FP64',
                windows=len(windows),example_rejection=example)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=check(args.folder)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='example_rejection'}))


if __name__=='__main__':main()
