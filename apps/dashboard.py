"""HTTP dashboard reading IN-CSE only; never generates or analyzes samples."""
import argparse
import json
import threading
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import config as c
from onem2m_client import Client, OneM2MError
from resource_registry import discover_machines, latest_or_none
from group_queries import latest_group
PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QuietFix · 설비 모니터</title>
<style>
:root{font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;color:#172b42;background:#f3f6fa}*{box-sizing:border-box}body{margin:0}header{background:#fff;border-bottom:1px solid #dce4ee;padding:25px max(24px,calc((100vw - 1380px)/2));display:flex;justify-content:space-between;gap:20px;align-items:center}h1{margin:0;font-size:26px;letter-spacing:-1px}.brand{color:#087e8b}.subtitle{font-size:13px;color:#607187;margin:7px 0 0}.clock{text-align:right;font-variant-numeric:tabular-nums;font-weight:650}.clock small{display:block;color:#66788f;font-size:11px;margin-bottom:5px}main{max-width:1428px;margin:auto;padding:28px 24px}.statusbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:22px;font-size:13px;color:#576b80}.demo{background:#e2f1f3;color:#11646d;padding:7px 12px;border-radius:7px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:22px}.machines{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-content:start}.machine{background:white;border:2px solid #dbe4ee;border-radius:15px;padding:23px;min-width:0}.machine.normal{border-color:#8bcbb6}.machine.abnormal{border-color:#df3d4e;box-shadow:0 0 0 3px #df3d4e12}.machine.abnormal .state-note{color:#b82235}.machine-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.machine h2{font-size:19px;margin:0}.machine-id{font-size:12px;color:#77889b;margin-top:5px}.badge{font-size:11px;font-weight:800;border-radius:7px;padding:7px 9px;background:#edf1f6;color:#617184}.normal .badge{background:#e1f5ec;color:#176449}.abnormal .badge{background:#ffe6e9;color:#b82235}.state-note{font-size:13px;color:#65788d;margin:22px 0}.metric{padding:17px 0;border-top:1px solid #eef1f5;display:flex;justify-content:space-between;align-items:center;gap:8px}.metric-label{color:#5b6d83;font-size:14px}.metric-value{font-size:29px;font-weight:700;font-variant-numeric:tabular-nums}.sensor-detail{display:block;font-size:11px;color:#718196;margin-top:5px}.metric.abnormal .metric-value{color:#b82235}.unit{font-size:12px;color:#738399;font-weight:400;margin-left:6px}.meta{border-top:1px solid #eef1f5;padding-top:16px;margin-top:5px;font-size:12px;color:#718196;line-height:1.9}.alerts{background:#fff;border:1px solid #dce4ee;border-radius:15px;padding:22px;align-self:start}.alerts-head{display:flex;justify-content:space-between;align-items:center}.alerts h2{font-size:17px;margin:0}.count{font-size:12px;color:#bc3042;background:#ffe9ec;padding:5px 8px;border-radius:6px}.alerts-note{font-size:12px;color:#7a899c;line-height:1.7}.alert-list{list-style:none;margin:18px 0 0;padding:0;max-height:620px;overflow:auto}.alert-item{border-left:3px solid #df3d4e;background:#fff6f7;border-radius:0 7px 7px 0;padding:12px;margin:0 0 10px}.alert-title{font-size:13px;font-weight:700;color:#a72b3d}.alert-time{font-size:11px;color:#7b7180;margin-top:6px;line-height:1.7}.empty{color:#798a9d;font-size:13px;padding:30px 0;text-align:center}.error{color:#b82235!important}.footer{font-size:12px;color:#74869a;margin-top:20px;line-height:1.8}@media(max-width:1100px){.layout{grid-template-columns:1fr}.alerts{width:100%}}@media(max-width:650px){header{align-items:flex-start;padding:20px}.clock{font-size:12px}.machines{grid-template-columns:1fr}main{padding:20px 14px}.statusbar{align-items:flex-start;flex-direction:column}.machine{padding:20px}}
</style></head><body>
<header><div><h1><span class="brand">QuietFix</span> 설비 모니터</h1><p class="subtitle">엣지 분석 결과 · 중앙 데이터 모니터링</p></div><div class="clock"><small>현재 시각 · 브라우저 현지 시간</small><time id="clock">—</time></div></header>
<main><div class="statusbar"><span class="demo">테스트 데이터 · 규칙 기반 분석</span><span id="connection" role="status">IN-CSE 연결 확인 중…</span></div><div class="layout"><section class="machines" id="machines" aria-label="설비별 상태"></section><aside class="alerts"><div class="alerts-head"><h2>이상 감지 알림</h2><span class="count" id="count">0 / 10</span></div><p class="alerts-note">최근 10건 · 새 이상 분석 샘플마다 등록<br>메모리 보관 · 재시작 시 저장 결과 재조회</p><ol class="alert-list" id="alerts"></ol></aside></div><p class="footer">센서값은 머신별 최신 샘플입니다. 미판정 센서는 정상 판정에 포함하지 않습니다. 분석 결과는 같은 sample_id의 측정값과 연결합니다. 통신이 끊기면 마지막 조회 화면을 유지합니다.</p></main>
<script>
const $=id=>document.getElementById(id);
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function date(value){if(!value)return '—';const d=new Date(value);return Number.isNaN(d.getTime())?'—':d.toLocaleString('ko-KR',{hour12:false})}
function tick(){$('clock').textContent=new Date().toLocaleString('ko-KR',{hour12:false})}tick();setInterval(tick,1000);
function metric(label,value,unit){const row=el('div','metric');row.append(el('span','metric-label',label));const v=el('span','metric-value',typeof value==='number'?value.toLocaleString('ko-KR',{maximumFractionDigits:2}):'—');v.append(el('span','unit',unit));row.append(v);return row}
function render(data){
  $('machines').replaceChildren();
  if(!data.machines.length)$('machines').append(el('p','empty','등록된 머신이 없습니다. 수집기 전송을 기다립니다.'));
  for(const m of data.machines){
    const t=m.telemetry||{},a=m.analysis;
    const state=a&&m.state==='ready'?a.status:'waiting';
    const card=el('article','machine '+(state==='abnormal'?'abnormal':state==='normal'?'normal':''));
    const head=el('div','machine-head'),title=el('div');
    title.append(el('h2','',m.machine_name||m.machine_id),el('div','machine-id',`${m.collector_id} / ${m.machine_id}`));
    head.append(title,el('span','badge',state==='abnormal'?'ABNORMAL':state==='normal'?'NORMAL':state==='unassessed'?'미판정':'대기 중'));
    let note=state==='abnormal'?'이상 상태가 감지되었습니다':state==='normal'?'판정 가능한 센서는 정상 범위입니다':state==='unassessed'?'판정 규칙이 있는 센서가 없습니다':m.state==='waiting_for_data'?'측정 데이터 수신 대기':'해당 측정값의 분석 결과 대기';
    if(a?.coverage==='partial')note+=' · 미판정 센서 포함';
    card.append(head,el('p','state-note',note));
    const readings=new Map((t.sensors||[]).map(s=>[s.sensor_id,s]));
    const analyzed=new Map((a?.sensors||[]).map(s=>[s.sensor_id,s.status]));
    for(const sensor of m.sensors){
      const reading=readings.get(sensor.sensor_id);
      const status=reading?analyzed.get(sensor.sensor_id):'missing';
      const row=metric(reading?.label||sensor.label,reading?.value,reading?.unit??sensor.unit);
      if(status==='abnormal')row.classList.add('abnormal');
      const detail=el('small','sensor-detail',`${sensor.sensor_id} · ${sensor.type} · ${status==='abnormal'?'이상':status==='normal'?'정상':status==='missing'?'이번 샘플 미수신':a?'미판정':'분석 대기'}`);
      row.querySelector('.metric-label').append(detail);
      card.append(row);
    }
    const meta=el('div','meta');
    meta.append(el('div','',`등록 센서 ${m.sensors.length}개 · 이번 샘플 ${(t.sensors||[]).length}개`),el('div','',`측정 전송 시각  ${date(t.timestamp)}`),el('div','',`분석 방식  ${a?.method==='demo_threshold_rule'?'임계값 규칙':a?.method||'대기 중'}`));
    card.append(meta);$('machines').append(card);
  }
  $('alerts').replaceChildren();$('count').textContent=`${data.alerts.length} / 10`;
  if(!data.alerts.length)$('alerts').append(el('li','empty','감지된 이상 알림이 없습니다'));
  for(const a of data.alerts){
    const item=el('li','alert-item');
    const bad=(a.sensors||[]).filter(s=>s.status==='abnormal').map(s=>s.label).join(', ');
    item.append(el('div','alert-title',`${a.machine_id} · 이상 감지`),el('div','alert-time',`${a.collector_id||'기존 수집기'}${bad?' · '+bad:''}`),el('div','alert-time',`측정 ${date(a.timestamp)}`),el('div','alert-time',`확인 ${date(a.detected_at)}`));$('alerts').append(item);
  }
}
async function update(){try{const r=await fetch('/api',{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'조회 실패');render(d);$('connection').className=d.error?'error':'';$('connection').textContent=d.error?'연결 오류 · 마지막 조회 데이터 표시':`IN-CSE 연결됨 · 마지막 조회 ${date(d.updated_at)}`}catch(e){$('connection').className='error';$('connection').textContent='연결 오류 · 마지막 조회 화면 유지'}finally{setTimeout(update,3000)}}update();
</script></body></html>"""
def snapshot():
    client = Client(c.IN_URL)
    # A dashboard can start before the forwarder provisions the archive.
    results = []
    try:
        results = list(client.records(c.IN_BASE+'/archive/results'))
        registered = list(discover_machines(client, c.IN_BASE+'/archive'))
    except OneM2MError as e:
        if e.status != 404:
            raise
        registered = []
    by_sample = {(r.get('collector_id'), r['machine_id'], r['sample_id']): r for r in results}
    grouped = latest_group(client) if registered else {}
    machines = []
    for machine in registered:
        info = {k: machine[k] for k in ('collector_id', 'machine_id', 'machine_name', 'sensors')}
        sample = grouped.get((machine['collector_id'], machine['machine_id']))
        if sample is None:
            sample = latest_or_none(client, machine['path']+'/telemetry')
        if sample is None:
            machines.append({**info, 'state': 'waiting_for_data'})
            continue
        matching = by_sample.get((machine['collector_id'], machine['machine_id'], sample['sample_id']))
        machines.append({**info, 'telemetry': sample, 'analysis': matching,
                         'state': 'ready' if matching else 'waiting_for_analysis'})
    return {'source': 'IN-CSE', 'machines': machines, '_results': results}
class DashboardCache:
    """One background poller for all browsers. Alerts never touch a database."""
    def __init__(self):
        self.lock = threading.Lock()
        self.alerts = deque(maxlen=10)
        self.seen = set()
        self.data = None
        self.error = None

    def refresh(self):
        try:
            value = snapshot()
            now = datetime.now(timezone.utc).isoformat()
            results = value.pop('_results')
            keys = {(r.get('collector_id'), r['machine_id'], r['sample_id']) for r in results}
            with self.lock:
                for r in sorted(results, key=lambda r: r.get('timestamp', '')):
                    key = (r.get('collector_id'), r['machine_id'], r['sample_id'])
                    if r.get('status') == 'abnormal' and key not in self.seen:
                        self.alerts.appendleft({**r, 'detected_at': now})
                # Bounded by CSE's retained result set, not by server uptime.
                self.seen = keys
                self.data = {**value, 'updated_at': now}
                self.error = None
        except Exception as e:
            with self.lock:
                self.error = str(e)

    def read(self):
        with self.lock:
            if self.data is None:
                return 503, {'error': self.error or '첫 데이터 조회 중'}
            return 200, {**self.data, 'alerts': list(self.alerts), 'error': self.error}

    def run(self, stop):
        while not stop.is_set():
            self.refresh()
            stop.wait(3)

CACHE = DashboardCache()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = 200
        if self.path == '/':
            body, kind = PAGE.encode(), 'text/html; charset=utf-8'
        elif self.path == '/api':
            status, value = CACHE.read()
            body, kind = json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8'
        else:
            status, body, kind = 404, b'Not found', 'text/plain'
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8090)
    a = p.parse_args()
    print(f'Dashboard http://{a.host}:{a.port}', flush=True)
    stop = threading.Event()
    thread = threading.Thread(target=CACHE.run, args=(stop,), daemon=True)
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    thread.start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
