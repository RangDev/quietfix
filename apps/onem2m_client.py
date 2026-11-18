"""Shared oneM2M HTTP operations. No application scheduling here."""
import hashlib
import json
import uuid
import requests
import config as c
class OneM2MError(RuntimeError):
    def __init__(self, response):
        self.status = response.status_code
        super().__init__(f'HTTP {self.status}: {response.text[:400]}')
class Client:
    def __init__(self, url, origin=None):
        self.url = url.rstrip('/')
        self.origin = origin or c.ORIGIN
    def call(self, method, path, body=None, ty=None, origin=None):
        headers = {'X-M2M-Origin': origin or self.origin, 'X-M2M-RI': uuid.uuid4().hex,
                   'X-M2M-RVI': '3', 'Accept': 'application/json'}
        if body is not None:
            headers['Content-Type'] = 'application/json' + (f';ty={ty}' if ty else '')
        from transport_security import http_options
        options=http_options(origin or self.origin)
        if 'cert' in options and not self.url.startswith('https://'):
            raise ValueError('Authenticated HTTP mode requires HTTPS')
        r = requests.request(method, self.url+'/'+path.lstrip('/'), headers=headers,
                             json=body, timeout=c.TIMEOUT, allow_redirects=False, **options)
        if not r.ok:
            raise OneM2MError(r)
        rsc = r.headers.get('X-M2M-RSC')
        if rsc and int(rsc) >= 4000:
            raise RuntimeError(f'oneM2M RSC {rsc}: {r.text[:400]}')
        return r.json() if r.content else {}
    def ensure(self, parent, kind, attrs, ty):
        try:
            return self.call('GET', parent+'/'+attrs['rn'])
        except OneM2MError as e:
            if e.status != 404:
                raise
        try:
            return self.call('POST', parent, {kind: attrs}, ty,
                             origin='Cqf'+attrs['rn'] if ty == 2 else None)
        except OneM2MError as e:
            if e.status != 409:
                raise
            return self.call('GET', parent+'/'+attrs['rn'])
    def put(self, container, data):
        # Immutable deterministic CIN name makes retry after a lost response safe.
        rn = 'qf-' + hashlib.sha256(data['sample_id'].encode()).hexdigest()
        try:
            self.call('POST', container, {'m2m:cin': {'rn': rn,
                      'cnf': 'application/json:0', 'con': json.dumps(data, ensure_ascii=False)}}, 4)
        except OneM2MError as e:
            if e.status != 409:
                raise
            existing = self.content(self.call('GET', container+'/'+rn)['m2m:cin'])
            if existing != data:
                raise RuntimeError('CIN name collision: existing content differs')
    @staticmethod
    def content(cin):
        v = cin['con']
        return json.loads(v) if isinstance(v, str) else v
    def records(self, container):
        # Discover all retained CINs, rather than only /la (which can skip samples).
        result = self.call('GET', container+'?fu=1&ty=4&drt=1&lim=10000')
        for uri in result.get('m2m:uril', []):
            yield self.content(self.call('GET', uri)['m2m:cin'])
    def latest(self, container):
        return self.content(self.call('GET', container+'/la')['m2m:cin'])

# Collector transport selection is explicit; other applications remain HTTP.
import atexit
import threading
_collector_clients = {}
_collector_lock = threading.Lock()
def collector_client():
    if c.COLLECTOR_PROTOCOL == 'http':
        return Client(c.MN_URL,c.role_origin('collector'))
    if c.COLLECTOR_PROTOCOL != 'mqtt':
        raise ValueError('QF_COLLECTOR_PROTOCOL must be http or mqtt')
    if not c.ACP_ENABLED:
        raise ValueError('MQTT collector requires QF_ACP_ENABLED=1 and pre-provisioned AEs')
    from mqtt_client import MQTTClient
    origin=c.role_origin('collector')
    key=(c.MN_URL,origin,c.MQTT_URL,c.MQTT_CSE_ID,c.MQTT_TOPIC_PREFIX)
    with _collector_lock:
        if key not in _collector_clients:
            _collector_clients[key]=MQTTClient(c.MN_URL,origin)
        return _collector_clients[key]

def close_collector_clients():
    with _collector_lock:
        clients=list(_collector_clients.values());_collector_clients.clear()
    for client in clients:client.close()
atexit.register(close_collector_clients)
