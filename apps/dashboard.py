
import argparse
import json
import threading
from time import monotonic
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
    return [{'id':item['id'],'name':item['name']} for item in sections]+[{'id':'unassigned','name':'Unassigned'}],mapping

def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (AttributeError, TypeError, ValueError):
        return None

def analysis_view(sample, results, now):
    sample_time = timestamp(sample.get('timestamp'))
    eligible = [r for r in results if r.get('sample_id') == sample['sample_id'] or
                (sample_time is not None and timestamp(r.get('timestamp')) is not None
                 and timestamp(r['timestamp']) <= sample_time)]
    latest = max(eligible, key=lambda r: (timestamp(r.get('timestamp')) or
                 datetime.min.replace(tzinfo=timezone.utc), r.get('sequence', 0)), default=None)
    pending = latest is None or latest['sample_id'] != sample['sample_id']
    reference = timestamp(latest.get('timestamp')) if latest else sample_time
    age = max(0, (now - reference).total_seconds()) if reference else None
    return {'analysis': latest, 'state': 'ready' if latest else 'waiting_for_analysis',
            'analysis_pending': pending, 'analysis_age_seconds': age,
            'analysis_delayed': age is None or age >= c.ANALYSIS_STALE_SECONDS}

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
    by_machine = {}
    for result in results:
        by_machine.setdefault((result.get('collector_id'), result['machine_id']), []).append(result)
    now = datetime.now(timezone.utc)
    grouped = latest_group(client) if registered else {}
    machines = []
    for machine in registered:
        info = {k: machine[k] for k in ('collector_id', 'machine_id', 'machine_name', 'sensors')}
        info.update(assignments.get((info['collector_id'],info['machine_id']),{'section_id':'unassigned','section_name':'Unassigned'}))
        sample = grouped.get((machine['collector_id'], machine['machine_id']))
        if sample is None:
            sample = latest_or_none(client, machine['path']+'/telemetry')
        if sample is None:
            machines.append({**info, 'state': 'waiting_for_data'})
            continue
        if c.FLEX_ENABLED:
            from flex_model import with_typed_readings
            sample = with_typed_readings(sample, machine)
        view = analysis_view(sample, by_machine.get((machine['collector_id'], machine['machine_id']), []), now)
        machines.append({**info, 'telemetry': sample, **view})
    return {'source': 'IN-CSE', 'machines': machines, 'sections':sections, '_results': results}
class DashboardCache:

    def __init__(self):
        self.lock = threading.Lock()
        self.alerts = deque(maxlen=10)
        self.seen = set()
        self.data = None
        self.error = None
        self.waiting_since = {}

    def refresh(self):
        try:
            value = snapshot()
            now = datetime.now(timezone.utc).isoformat()
            results = value.pop('_results')
            keys = {(r.get('collector_id'), r['machine_id'], r['sample_id']) for r in results}
            with self.lock:
                waiting = {}
                observed_at = monotonic()
                for machine in value['machines']:
                    if machine.get('telemetry') and not machine.get('analysis'):
                        key = (machine['collector_id'], machine['machine_id'])
                        waiting[key] = self.waiting_since.get(key, observed_at)
                        machine['analysis_wait_seconds'] = observed_at - waiting[key]
                        machine['analysis_delayed'] = machine.get('analysis_delayed', False) or (
                            machine['analysis_wait_seconds'] >= c.ANALYSIS_STALE_SECONDS)
                self.waiting_since = waiting
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
                return 503, {'error': self.error or 'Retrieving initial data'}
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


