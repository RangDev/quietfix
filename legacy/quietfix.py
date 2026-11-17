"""Local QuietFix teaching prototype. Polling, deterministic simulated data."""
import argparse, json, os, time, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import requests

MN=os.getenv('QF_MN_URL','http://127.0.0.1:8081').rstrip('/')
IN=os.getenv('QF_IN_URL','http://127.0.0.1:8080').rstrip('/')
BASE=os.environ['QF_MN_BASE']; CENTRAL='quietfix-in'
MN_ID=os.environ['QF_MN_ID']
if os.getenv('QF_LOCAL_INSECURE')=='1':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY=os.getenv('QF_LOCAL_INSECURE')!='1'

def call(method, host, path, body=None, ty=None, origin="CAdmin"):
    h={'X-M2M-Origin':origin,'X-M2M-RI':uuid.uuid4().hex,'X-M2M-RVI':'3','Accept':'application/json'}
    if body is not None: h['Content-Type']='application/json'+(f';ty={ty}' if ty else '')
    r=requests.request(method,host+'/'+path.lstrip('/'),headers=h,json=body,timeout=15,verify=VERIFY)
    if not r.ok: raise RuntimeError(f'{method} {r.url}: HTTP {r.status_code}: {r.text[:600]}')
    return r.json() if r.content else {}

def ensure(host,path,kind,attrs,ty):
    # Only a real NOT_FOUND permits creation; never mask authentication/network errors.
    h={'X-M2M-Origin':'CAdmin','X-M2M-RI':uuid.uuid4().hex,'X-M2M-RVI':'3'}
    r=requests.get(host+'/'+path+'/'+attrs['rn'],headers=h,timeout=15,verify=VERIFY)
    if r.status_code==404: return call('POST',host,path,{kind:attrs},ty, origin=('Cqf'+attrs['rn'] if ty==2 else 'CAdmin'))
    if not r.ok: raise RuntimeError(f'GET: {r.status_code} {r.text}')
    return r.json()

def setup():
    ensure(MN,BASE,'m2m:acp',{'rn':'central-read','pv':{'acr':[{'acor':['CAdmin'],'acop':63},{'acor':['/quietfix-in-id/CAdmin'],'acop':2}]},'pvs':{'acr':[{'acor':['CAdmin'],'acop':63}]}},1)
    for host,base,names in [(MN,BASE,['collector-01','collector-02','analyzer']),
                            (IN,CENTRAL,['archive','dashboard'])]:
        for name in names:
            ensure(host,base,'m2m:ae',{'rn':name,'api':'NQuietFix','rr':False,'srv':['3']},2)
            containers=['results'] if name=='analyzer' else ['telemetry']
            if name=='archive': containers=['machine-01','machine-02','results']
            if name=='dashboard': containers=[]
            for c in containers:
                ensure(host,base+'/'+name,'m2m:cnt',{'rn':c,'mni':1000},3)
                if host==MN:
                    call('PUT',host,base+'/'+name+'/'+c,{'m2m:cnt':{'acpi':[BASE+'/central-read']}})
    print('SETUP PASS: collector-01, collector-02, analyzer, archive, dashboard')

def put(host,path,data):
    # con is a JSON string for portable oneM2M content handling.
    call('POST',host,path,{'m2m:cin':{'cnf':'application/json:0','con':json.dumps(data)}},4)

def latest(host,path):
    value=call('GET',host,path+'/la')['m2m:cin']['con']
    return json.loads(value) if isinstance(value,str) else value

def step(mode):
    now=datetime.now(timezone.utc).isoformat()
    for n in (1,2):
        bad=mode=='fault' and n==2
        sample={'sample_id':uuid.uuid4().hex,'machine_id':f'machine-{n:02}',
                'timestamp':now,'simulated':True,'temperature_c':82 if bad else 45+n,
                'vibration_rms_mm_s':9 if bad else 2,'current_a':7 if bad else 3}
        path=f'{BASE}/collector-{n:02}/telemetry'
        put(MN,path,sample)
        # Analysis consumes the actual CSE record rather than the local sample.
        read=latest(MN,path)
        result={k:read[k] for k in ('sample_id','machine_id','timestamp','simulated')}
        result['status']='abnormal' if read['temperature_c']>=75 or read['vibration_rms_mm_s']>=7 else 'normal'
        result['method']='demo_threshold_rule'
        put(MN,BASE+'/analyzer/results',result)
        put(IN,f'{CENTRAL}/archive/machine-{n:02}',read)
        put(IN,CENTRAL+'/archive/results',result)
        print(read['machine_id'],result['status'],flush=True)

def check():
    a=call('GET',IN,CENTRAL)['m2m:cb']; b=call('GET',MN,BASE)['m2m:cb']
    assert a['cst']==1 and b['cst']==2,(a,b)
    csr=call('GET',IN,CENTRAL+'?fu=1&ty=16')
    assert csr.get('m2m:uril'),csr
    assert '/'+MN_ID==call('GET',IN,CENTRAL+'/'+MN_ID)['m2m:csr']['csi']
    remote=latest(IN,'~/'+MN_ID+'/'+BASE+'/collector-02/telemetry')
    local=latest(MN,BASE+'/collector-02/telemetry')
    archive=latest(IN,CENTRAL+'/archive/machine-02')
    assert remote['sample_id']==local['sample_id']==archive['sample_id']
    print('CHECK PASS: IN=1 MN=2, Mcc registration, remote retrieval, archive match')

PAGE='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>QuietFix</title>
<style>body{font:18px sans-serif;max-width:900px;margin:40px auto;background:#eef2f6;color:#172b45}pre{background:white;padding:24px;white-space:pre-wrap;border-radius:12px}</style>
<h1>QuietFix 로컬 대시보드</h1><p>가상 센서 데이터 · 규칙 기반 판정 · 3초마다 갱신</p><pre id="v">로딩 중</pre>
<script>async function update(){try{let r=await fetch('/api');document.querySelector('#v').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.querySelector('#v').textContent=String(e)}}update();setInterval(update,3000)</script></html>'''
def serve():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status=200
            if self.path=='/api':
                try:
                    out={'simulated':True,'machines':[latest(IN,f'{CENTRAL}/archive/machine-{n:02}') for n in (1,2)],
                         'latest_result':latest(IN,CENTRAL+'/archive/results')}
                except Exception as e: status=503;out={'error':str(e)}
                data=json.dumps(out,ensure_ascii=False).encode();ctype='application/json; charset=utf-8'
            else: data=PAGE.encode();ctype='text/html; charset=utf-8'
            self.send_response(status);self.send_header('Content-Type',ctype);self.end_headers();self.wfile.write(data)
    print('Dashboard http://127.0.0.1:8090 (SSH tunnel from Windows)',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8090),Handler).serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['setup','step','run','check','serve'])
    p.add_argument('--mode',choices=['normal','fault'],default='normal');a=p.parse_args()
    try:
        if a.command=='setup':setup()
        elif a.command=='step':step(a.mode)
        elif a.command=='check':check()
        elif a.command=='serve':serve()
        else:
            while True:step(a.mode);time.sleep(5)
    except KeyboardInterrupt:pass
    except Exception as e:raise SystemExit(str(e))
