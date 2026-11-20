
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
from pathlib import Path
import os
PAGE = (c.ROOT/'dashboard.html').read_text(encoding='utf-8')

def section_settings():
    path=Path(os.getenv('QF_DASHBOARD_SECTIONS',str(c.ROOT/'dashboard_sections.json')))
    raw=json.loads(path.read_text(encoding='utf-8'))
    sections=raw['sections'];mapping={};seen=set()
    if not isinstance(sections,list):raise ValueError('Dashboard sections must be a list')
    for section in sections:
        sid,name=section['id'],section['name']
        if not isinstance(sid,str) or not sid or sid=='unassigned' or sid in seen or not isinstance(name,str) or not name:
            raise ValueError('Invalid or duplicate dashboard section')
        seen.add(sid)
        for machine in section['machines']:
            key=(machine['collector_id'],machine['machine_id'])
            if not all(isinstance(value,str) and value for value in key) or key in mapping:
                raise ValueError('A machine must belong to only one dashboard section')
            mapping[key]={'section_id':sid,'section_name':name}
    return [{'id':item['id'],'name':item['name']} for item in sections]+[{'id':'unassigned','name':'\ubbf8\ubc30\uc815'}],mapping

def snapshot():
    sections,assignments=section_settings()
    client = Client(c.IN_URL, c.role_origin('dashboard'))

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
        info.update(assignments.get((info['collector_id'],info['machine_id']),{'section_id':'unassigned','section_name':'\ubbf8\ubc30\uc815'}))
        sample = grouped.get((machine['collector_id'], machine['machine_id']))
        if sample is None:
            sample = latest_or_none(client, machine['path']+'/telemetry')
        if sample is None:
            machines.append({**info, 'state': 'waiting_for_data'})
            continue
        if c.FLEX_ENABLED:
            from flex_model import with_typed_readings
            sample = with_typed_readings(sample, machine)
        matching = by_sample.get((machine['collector_id'], machine['machine_id'], sample['sample_id']))
        machines.append({**info, 'telemetry': sample, 'analysis': matching,
                         'state': 'ready' if matching else 'waiting_for_analysis'})
    return {'source': 'IN-CSE', 'machines': machines, 'sections':sections, '_results': results}
class DashboardCache:

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

                self.seen = keys
                self.data = {**value, 'updated_at': now}
                self.error = None
        except Exception as e:
            with self.lock:
                self.error = str(e)

    def read(self):
        with self.lock:
            if self.data is None:
                return 503, {'error': self.error or '\uccab \ub370\uc774\ud130 \uc870\ud68c \uc911'}
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

