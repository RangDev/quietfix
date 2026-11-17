"""Optional shared resource provisioning. Collectors also register themselves."""
import config as c
from onem2m_client import Client
from resource_registry import ensure_ae, ensure_analyzer, ensure_archive

def main():
    c.require_mn()
    ensure_ae(Client(c.MN_URL), c.MN_BASE, c.COLLECTOR_ID)
    ensure_analyzer(Client(c.MN_URL))
    ensure_archive(Client(c.IN_URL))
    ensure_ae(Client(c.IN_URL), c.IN_BASE, 'dashboard')
    print('Shared resources ready. Machines/sensors register on first measurement.')
if __name__ == '__main__':
    main()
