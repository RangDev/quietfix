"""Notification wake-ups plus periodic retained-data reconciliation."""
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import config as c
from resource_registry import discover_machines, ensure_analyzer

class Notifications:
    def __init__(self, host, port):
        self.wake = threading.Event()
        wake = self.wake
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                try:
                    if os.getenv('QF_NOTIFY_CERT_FILE'):
                        from transport_security import peer_name
                        if peer_name(self.connection) not in os.getenv('QF_NOTIFY_PEERS','').split(','):
                            self.send_error(403);return
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 1048576:
                        raise ValueError('Invalid body size')
                    signal = json.loads(self.rfile.read(size))['m2m:sgn']
                    if not isinstance(signal, dict):
                        raise ValueError('Invalid signal')
                    if not signal.get('vrq'):
                        wake.set()
                    self.send_response(200)
                    self.send_header('X-M2M-RSC', '2000')
                    self.send_header('X-M2M-RI', self.headers.get('X-M2M-RI', ''))
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                except (ValueError, KeyError, TypeError):
                    self.send_error(400)
        self.server = ThreadingHTTPServer((host, port), Handler)
        if os.getenv('QF_NOTIFY_CERT_FILE'):
            from transport_security import server_context
            if not os.getenv('QF_NOTIFY_PEERS'):raise ValueError('Set QF_NOTIFY_PEERS for authenticated notifications')
            self.server.socket=server_context(os.environ['QF_NOTIFY_CERT_FILE'],os.environ['QF_NOTIFY_KEY_FILE'],os.environ['QF_NOTIFY_CA_FILE']).wrap_socket(self.server.socket,server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

from routing import guarded

@guarded
def subscribe(client, role, url):
    paths = [m['path']+'/telemetry' for m in discover_machines(client, c.MN_BASE)]
    if role == 'forwarder':
        paths.append(ensure_analyzer(client))
    for path in paths:
        name = 'qf-'+role
        attrs = {'rn': name, 'enc': {'net': [3]}, 'nu': [url], 'nct': 1}
        if c.ACP_ENABLED:
            from access_control import policy_ref
            attrs['acpi'] = [policy_ref(c.MN_BASE, role+'-sub')]
        existing = client.ensure(path, 'm2m:sub', attrs, 23)['m2m:sub']
        if any(existing.get(k) != attrs[k] for k in ('nu', 'enc', 'nct')):
            client.call('PUT', path+'/'+name, {'m2m:sub': {k: attrs[k] for k in ('nu','enc','nct')}})

def run(role, client, step, once=False):
    if once:
        step()
        return
    url = getattr(c, role.upper()+'_NOTIFY_URL')
    if not url:
        logging.warning('%s: notification URL unset; using polling', role)
        while True:
            try:
                step()
            except Exception:
                logging.exception('%s reconciliation failed', role)
            threading.Event().wait(max(c.POLL_SECONDS, .1))
    # Receiver must be live before creating subscriptions (verification requests).
    with Notifications(c.NOTIFY_HOST, getattr(c, role.upper()+'_NOTIFY_PORT')) as receiver:
        while True:
            receiver.wake.clear()
            try:
                subscribe(client, role, url)
            except Exception:
                logging.exception('%s subscription setup failed; retrying at next reconciliation', role)
            try:
                step()
            except Exception:
                logging.exception('%s reconciliation failed', role)
            # A notification during processing stays set: no wake-up is lost.
            receiver.wake.wait(max(c.RECONCILE_SECONDS, .1))
