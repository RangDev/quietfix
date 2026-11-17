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
MACHINES = ('machine-01', 'machine-02')
def telemetry(machine):
    if machine not in MACHINES:
        raise ValueError(f'Unsupported machine: {machine}')
    return f'{MN_BASE}/collector-{machine[-2:]}/telemetry'
def require_mn():
    if not MN_BASE:
        raise SystemExit('QF_MN_BASE is missing. Run: source session.env')
