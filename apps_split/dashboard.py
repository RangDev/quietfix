"""HTTP dashboard reading IN-CSE only; never generates or analyzes samples."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import config as c
from onem2m_client import Client, OneM2MError
PAGE = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>QuietFix</title>
<h1>QuietFix 테스트 대시보드</h1><p>JSON 테스트 데이터 · 규칙 기반 판정 · 3초마다 조회</p>
<pre id="v">로딩 중</pre><script>
async function update(){try{let r=await fetch('/api');document.getElementById('v').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.getElementById('v').textContent=String(e)}}
update();setInterval(update,3000);</script></html>"""
def snapshot():
    client = Client(c.IN_URL)
    results = list(client.records(c.IN_BASE+'/archive/results'))
    machines = []
    for machine in c.MACHINES:
        try:
            sample = client.latest(f'{c.IN_BASE}/archive/{machine}')
        except OneM2MError as e:
            if e.status != 404:
                raise
            machines.append({'machine_id':machine, 'state':'waiting_for_data'})
            continue
        matching = next((r for r in results if r['machine_id']==machine and r['sample_id']==sample['sample_id']), None)
        machines.append({'telemetry':sample, 'analysis':matching,
                         'state':'ready' if matching else 'waiting_for_analysis'})
    return {'source':'IN-CSE', 'machines':machines}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = 200
        if self.path == '/':
            body, kind = PAGE.encode(), 'text/html; charset=utf-8'
        elif self.path == '/api':
            try:
                value = snapshot()
            except Exception as e:
                status, value = 503, {'error':str(e)}
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
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
