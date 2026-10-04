"""Small HTTP serving checks, not an optimization or throughput benchmark."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import datetime
import http.client
import json
import socket
import time
import urllib.error
import urllib.request

BASE='http://10.0.7.68:8095'
KEY=(Path.home()/'.config/fleet/q8-lan/api-key.txt').read_text().strip()
OUT=Path(__file__).with_name('http-validation.json')
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'client':'Windows fleet workspace, direct LAN HTTP', 'endpoint':BASE+'/v1',
        'scope':'Auth, small completion, streaming, FIFO queuing and disconnect recovery; not a capacity/throughput benchmark.',
        'checks':[]}

def save():OUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
def record(name,**extra):
    report['checks'].append(dict(name=name,passed=True,**extra));save();print(name+' passed',flush=True)
def call(path,body=None,auth=True,wrong=False):
    headers={'Content-Type':'application/json'}
    if auth:headers['Authorization']='Bearer '+('wrong-key' if wrong else KEY)
    req=urllib.request.Request(BASE+path,headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req,timeout=120) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
def payload(prompt,max_tokens=128,stream=False):
    return {'model':'flash-next-Q8_0','messages':[{'role':'user','content':prompt}],
            'max_tokens':max_tokens,'temperature':0,'reasoning_effort':'none','stream':stream}
def complete(prompt,max_tokens=128):
    started=time.time();status,data=call('/v1/chat/completions',payload(prompt,max_tokens))
    assert status==200,(status,data)
    text=data['choices'][0]['message'].get('content') or ''
    assert text.strip(),data
    return dict(started=started,finished=time.time(),response=data)
def wait_idle(timeout=20):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        code,s=call('/status')
        if code==200 and not s.get('busy') and not s.get('queued'):return s
        time.sleep(.2)
    raise AssertionError('Server did not return idle')

try:
    code,h=call('/health',auth=False)
    assert code==200 and h['loaded'] and h['api_key'] and h['max_context']==139264 and not h['images']
    record('health',response=h)
    for path,body in [('/v1/models',None),('/v1/chat/completions',payload('Say hello.')),('/settings',None)]:
        for wrong in (False,True):
            code,data=call(path,body,auth=wrong,wrong=wrong)
            assert code==401,(path,wrong,code,data)
    record('missing-and-wrong-key-rejected',paths=['/v1/models','/v1/chat/completions','/settings'])
    code,models=call('/v1/models')
    assert code==200 and models['data'][0]['id']=='flash-next-Q8_0'
    code,status=call('/v1/status')
    assert code==200 and status['concurrency']['serving']==1
    record('authenticated-model-discovery',models=models,concurrency=status['concurrency'])
    simple=complete('Reply with exactly: LAN test ready',64)
    record('nonstream-completion',result=simple)
    req=urllib.request.Request(BASE+'/v1/chat/completions',data=json.dumps(payload('Write a Python function add(a, b) that returns their sum. Output only code.',96,True)).encode(),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+KEY})
    chunks=[];done=False;text=''
    with urllib.request.urlopen(req,timeout=120) as r:
        assert r.status==200 and 'text/event-stream' in r.headers['Content-Type']
        for raw in r:
            if not raw.startswith(b'data: '):continue
            if raw.strip()==b'data: [DONE]':done=True;break
            c=json.loads(raw[6:]);chunks.append(c)
            for choice in c.get('choices',[]):text+=choice.get('delta',{}).get('content') or ''
    assert done and text.strip() and len(chunks)>1,(done,text)
    record('sse-streaming',chunks=len(chunks),text=text)
    wait_idle()
    prompt='Write a numbered list of the first 100 positive integers, one per line. Do not summarize or skip entries.'
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(complete,prompt,256)
        until=time.monotonic()+20
        while time.monotonic()<until:
            _,s=call('/status')
            if s.get('busy'):break
            assert not a.done(),'First request finished before FIFO probe'
            time.sleep(.05)
        else:raise AssertionError('No first active request observed')
        b=pool.submit(complete,'Reply with exactly: second queued request finished',64)
        queued=False;observations=[]
        while not (a.done() and b.done()):
            _,s=call('/status')
            q={'busy':s.get('busy'),'queued':s.get('queued')};observations.append(q)
            queued |= bool(s.get('queued'))
            time.sleep(.05)
        aa,bb=a.result(),b.result()
    assert queued,'No queued client observed'
    assert aa['finished']<=bb['finished'],(aa['finished'],bb['finished'])
    record('two-clients-fifo',queue_observed=queued,first=aa,second=bb,observations=observations)
    wait_idle()
    conn=http.client.HTTPConnection('10.0.7.68',8095,timeout=120)
    conn.request('POST','/v1/chat/completions',body=json.dumps(payload('Write a very long Python module implementing a binary search tree with insertion, deletion, traversal and extensive tests. Continue until all tests are implemented.',4096,True)),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+KEY})
    connection_socket=conn.sock  # HTTP/1.0 transfers socket ownership to the response.
    response=conn.getresponse();assert response.status==200
    seen=0
    while seen<8:
        raw=response.readline()
        assert raw,'Stream ended before cancellation probe'
        if raw.startswith(b'data: ') and raw.strip()!=b'data: [DONE]':seen+=1
    cancel_at=time.time()
    connection_socket.shutdown(socket.SHUT_RDWR)
    response.close();conn.close()
    idle=wait_idle()
    recovery=complete('Reply with exactly: recovery ready',64)
    record('disconnect-cancellation-and-following-request',chunks_before_disconnect=seen,
           idle_within_seconds=time.time()-cancel_at,recovered=recovery,
           final_status=idle)
    code,s=call('/v1/status')
    assert code==200 and s['activity']['in_flight']==0
    report.update(completed=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),final_status=s)
    save();print('All LAN checks passed',flush=True)
except Exception as e:
    report.update(completed=False,error=repr(e));save();raise
