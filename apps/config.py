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

MEASURE_PERIOD = float(os.getenv('QF_MEASURE_PERIOD', '1'))
NORMAL_PERIOD = float(os.getenv('QF_NORMAL_PERIOD', '5'))
ABNORMAL_PERIOD = float(os.getenv('QF_ABNORMAL_PERIOD', '1'))
OUTBOX_LIMIT = int(os.getenv('QF_OUTBOX_LIMIT', '10000'))

# Opt-in access control: legacy development commands remain unchanged by default.
ACP_ENABLED = os.getenv('QF_ACP_ENABLED') == '1'
ADMIN_ORIGIN = os.getenv('QF_ADMIN_ORIGIN', ORIGIN)
def role_origin(role):
    if not ACP_ENABLED:
        return ORIGIN
    defaults = {'collector': 'Cqf'+COLLECTOR_ID, 'analyzer': 'Cqfanalyzer',
                'forwarder': 'Cqfforwarder', 'dashboard': 'Cqfdashboard'}
    origin = os.getenv('QF_'+role.upper()+'_ORIGIN', defaults[role])
    if origin == ADMIN_ORIGIN:
        raise ValueError('Runtime role must not use the administrator origin')
    return origin

# Optional typed latest-value projection; CIN history remains unchanged.
FLEX_ENABLED = os.getenv('QF_FLEX_ENABLED') == '1'

COLLECTOR_PROTOCOL = os.getenv('QF_COLLECTOR_PROTOCOL', 'http').lower()
MQTT_URL = os.getenv('QF_MQTT_URL', 'mqtt://127.0.0.1:1883')
MQTT_CSE_ID = os.getenv('QF_MQTT_CSE_ID', '')
MQTT_TOPIC_PREFIX = os.getenv('QF_MQTT_TOPIC_PREFIX', '').rstrip('/')
MQTT_USERNAME = os.getenv('QF_MQTT_USERNAME', '')
MQTT_PASSWORD = os.getenv('QF_MQTT_PASSWORD', '')
MQTT_CA_FILE = os.getenv('QF_MQTT_CA_FILE')
