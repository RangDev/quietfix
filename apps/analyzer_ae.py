"""Independent analysis AE: consume MN telemetry and persist rule results."""
import argparse
import config as c
from onem2m_client import Client
from worker_state import State
from event_worker import run
from device_model import normalize, sensor_status
from resource_registry import discover_machines, ensure_analyzer

def analyze(sample):
    sensors = [{**s, 'status': sensor_status(s)} for s in normalize(sample)['sensors']]
    statuses = {s['status'] for s in sensors}
    status = 'abnormal' if 'abnormal' in statuses else 'normal' if 'normal' in statuses else 'unassessed'
    return {**{k: sample[k] for k in ('sample_id', 'collector_id', 'machine_id', 'timestamp', 'simulated')},
            'status': status, 'method': 'demo_threshold_rule', 'sensors': sensors,
            'coverage': 'partial' if 'unassessed' in statuses else 'complete'}

def step(client, state):
    results = ensure_analyzer(client)
    for machine in discover_machines(client, c.MN_BASE):
        for sample in client.records(machine['path']+'/telemetry'):
            key = 'v3:'+machine['collector_id']+':'+machine['machine_id']+':'+sample['sample_id']
            if state.has(key):
                continue
            result = analyze(sample)
            client.put(results, result)
            state.mark(key)
            print('ANALYZED', machine['machine_id'], result['status'], sample['sample_id'], flush=True)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--once', action='store_true')
    a = p.parse_args()
    c.require_mn()
    client, state = Client(c.MN_URL), State('analyzer')
    run('analyzer', client, lambda: step(client, state), a.once)
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
