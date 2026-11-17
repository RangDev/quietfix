"""Per-device environment configuration. Importing this module starts no service."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
STATE = Path(os.getenv('QF_STATE_DIR', str(ROOT / 'state')))
MN_URL = os.getenv('QF_MN_URL', 'http://127.0.0.1:8081').rstrip('/')
MN_BASE = os.getenv('QF_MN_BASE', '').strip('/')
IN_URL = os.getenv('QF_IN_URL', 'http://127.0.0.1:9090').rstrip('/')
IN_BASE = os.getenv('QF_IN_BASE', 'quietfix-in').strip('/')
ORIGIN = os.getenv('QF_ORIGIN', 'CAdmin')
VERIFY_TLS = os.getenv('QF_LOCAL_INSECURE') != '1'
POLL_SECONDS = float(os.getenv('QF_POLL_SECONDS', '2'))
TIMEOUT = float(os.getenv('QF_HTTP_TIMEOUT', '15'))
COLLECTOR_ID = os.getenv('QF_COLLECTOR_ID', 'collector-01')
def require_mn():
    if not MN_BASE:
        raise SystemExit('QF_MN_BASE is missing. Run: source session.env')

# Advertised URLs must be reachable FROM the MN-CSE container.
NOTIFY_HOST = os.getenv('QF_NOTIFY_HOST', '0.0.0.0')
ANALYZER_NOTIFY_PORT = int(os.getenv('QF_ANALYZER_NOTIFY_PORT', '8091'))
FORWARDER_NOTIFY_PORT = int(os.getenv('QF_FORWARDER_NOTIFY_PORT', '8092'))
ANALYZER_NOTIFY_URL = os.getenv('QF_ANALYZER_NOTIFY_URL', '')
FORWARDER_NOTIFY_URL = os.getenv('QF_FORWARDER_NOTIFY_URL', '')
RECONCILE_SECONDS = float(os.getenv('QF_RECONCILE_SECONDS', '30'))
