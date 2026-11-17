"""One-time provisioning of AE/container resources; does not launch ACME."""
import config as c
from onem2m_client import Client

def main():
    c.require_mn()
    for client, base, mapping in [
        (Client(c.MN_URL), c.MN_BASE, {'collector-01':['telemetry'], 'collector-02':['telemetry'], 'analyzer':['results']}),
        (Client(c.IN_URL), c.IN_BASE, {'archive':[*c.MACHINES, 'results'], 'dashboard':[]})]:
        for name, containers in mapping.items():
            client.ensure(base, 'm2m:ae', {'rn':name, 'api':'NQuietFix', 'rr':False, 'srv':['3']}, 2)
            for container in containers:
                client.ensure(base+'/'+name, 'm2m:cnt', {'rn':container, 'mni':1000}, 3)
    print('Resources ready. MN/IN are existing independent ACME servers.')
if __name__ == '__main__':
    main()
