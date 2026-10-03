"""Generate every catalog sample through a real Responses JSON-schema server.

The prompt requests a known valid sample: this tests schema admission, generation,
serialization and final validation, not model coding quality or adversarial schema
enforcement. Other native matcher/negative validation tests cover illegal output.
"""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from jsonschema import Draft202012Validator, FormatChecker


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--catalog',type=Path,default=Path(__file__).resolve().parents[1]/'docs/json-schema-examples.json')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--start-case',type=int,default=1,help='1-based catalog case to start at (diagnostic runs)')
    args=parser.parse_args()
    args.out.mkdir(exist_ok=False,parents=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    report={'scripted_engine':False,'prompt_requests_known_valid_sample':True,'cases':[],'result':'running'}
    try:
        for case in json.loads(args.catalog.read_text(encoding='utf-8'))[args.start_case-1:]:
            name,schema,sample=case['name'],case['schema'],case['sample']
            Draft202012Validator.check_schema(schema)
            validator=Draft202012Validator(schema,format_checker=FormatChecker())
            validator.validate(sample)
            body={'model':args.model,'store':False,'reasoning':{'effort':'none'},'max_output_tokens':512,'temperature':0,
                  'input':'Return exactly this JSON value, without explanation: '+json.dumps(sample,ensure_ascii=False),
                  'text':{'format':{'type':'json_schema','name':name.replace('-','_'),'strict':True,'schema':schema}}}
            (args.out/(name+'.request.json')).write_text(json.dumps(body,indent=2,ensure_ascii=False),encoding='utf-8')
            request=urllib.request.Request(args.base_url.rstrip('/')+'/responses',data=json.dumps(body).encode(),
                headers={'Authorization':'Bearer '+os.environ['STRATA_API_KEY'],'Content-Type':'application/json'})
            started=time.monotonic()
            try:
                response=opener.open(request,timeout=180)
            except urllib.error.HTTPError as error:
                response=error
            with response:
                status=response.status
                result=json.load(response)
            (args.out/(name+'.response.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
            row={'name':name,'http_status':status,'status':result.get('status'),'seconds':time.monotonic()-started}
            report['cases'].append(row)
            try:
                assert status==200 and result['status']=='completed',result.get('error')
                value=json.loads(''.join(p['text'] for item in result['output'] if item['type']=='message' for p in item['content']))
                validator.validate(value)
                assert value==sample,(value,sample)
                row['schema_valid']=True;row['sample_matches']=True
            except Exception as error:
                row['failure']=str(error)
            print(name,'FAIL' if 'failure' in row else 'PASS',round(row['seconds'],3),row.get('failure',''),flush=True)
        report['result']='fail' if any('failure' in row for row in report['cases']) else 'pass'
    except Exception as error:
        report['result']='fail';report['failure']=str(error)
        raise
    finally:
        (args.out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if report['result']!='pass':
        raise SystemExit(1)


if __name__=='__main__':main()
