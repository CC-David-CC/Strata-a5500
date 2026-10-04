"""Show next-token probabilities from a local Strata server, using only Python's standard library."""
import argparse
import json
import math
import os
import sys
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def show(entry):
    print(f"Generated {entry['token']!r}: {100*math.exp(entry['logprob']):.6f}% (logprob {entry['logprob']:.6f})")
    for alternative in entry['top_logprobs']:
        print(f"  {alternative['token']!r:24} {100*math.exp(alternative['logprob']):10.6f}%")


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    cases=sorted(p.stem for p in (ROOT/'examples/logprobs').glob('*.json'))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recorded',action='store_true',help='show the committed real-model first-token receipt; no server')
    parser.add_argument('--proposal',action='store_true',help='show a recorded MTP proposal versus target verification')
    parser.add_argument('--base-url',default=os.environ.get('STRATA_BASE_URL','http://127.0.0.1:8080'))
    parser.add_argument('--case',choices=cases,default='decision')
    args=parser.parse_args()
    if args.proposal:
        evidence=json.loads((ROOT/'docs/logprobs-evidence/native/edges/oracle.json').read_text(encoding='utf-8'))
        window=evidence['example_rejection']
        print('Recorded proposal; no inference run. Draft and target use separately labeled distributions.')
        for index, token in enumerate(window['proposal']):
            outcome='accepted' if index<window['accepted_proposals'] else 'rejected or after rejection'
            print(f"Token {token['token_id']}: draft {100*token['draft_probability']:.6f}%, "
                  f"target {100*math.exp(token['target_logprob']):.6f}% ({outcome})")
        return
    if args.recorded:
        response=json.loads((ROOT/'docs/logprobs-evidence/initial/json-response.txt').read_text(encoding='utf-8'))
        print('Recorded llm-49 result; this command did not run inference.')
        for entry in response['choices'][0]['logprobs']['content']: show(entry)
        return
    body=(ROOT/'examples/logprobs'/f'{args.case}.json').read_bytes()
    headers={'Content-Type':'application/json'}
    if os.environ.get('STRATA_API_KEY'): headers['Authorization']='Bearer '+os.environ['STRATA_API_KEY']
    request=urllib.request.Request(args.base_url.rstrip('/')+'/v1/chat/completions',data=body,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=600) as response:
            if json.loads(body).get('stream'):
                for line in response:
                    if not line.startswith(b'data: ') or line.strip()==b'data: [DONE]': continue
                    chunk=json.loads(line[6:])
                    if 'error' in chunk: raise RuntimeError(chunk['error'])
                    choice=chunk['choices'][0]
                    for entry in (choice.get('logprobs') or {}).get('content') or []: show(entry)
                    if choice['delta'].get('tool_calls'): print('Tool call:',choice['delta']['tool_calls'])
            else:
                choice=json.load(response)['choices'][0]
                print('Answer:',json.dumps(choice['message'],ensure_ascii=False))
                for entry in choice['logprobs']['content']: show(entry)
                if not choice['logprobs']['content']: print('No visible answer tokens; reasoning/tool syntax is not scored as content.')
    except urllib.error.HTTPError as exc:
        raise SystemExit(f'HTTP {exc.code}: {exc.read().decode()}') from None


if __name__=='__main__': main()
