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
        r = requests.request(method, self.url+'/'+path.lstrip('/'), headers=headers,
                             json=body, timeout=c.TIMEOUT, verify=c.VERIFY_TLS)
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
        return self.call('POST', parent, {kind: attrs}, ty,
                         origin='Cqf'+attrs['rn'] if ty == 2 else None)
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
