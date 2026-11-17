"""Independent polling AE: consume MN telemetry and persist rule results."""
import argparse
import logging
import time
import config as c
from onem2m_client import Client
from worker_state import State

def analyze(sample):
    bad = sample['temperature_c'] >= 75 or sample['vibration_rms_mm_s'] >= 7
    return {**{k: sample[k] for k in ('sample_id', 'machine_id', 'timestamp', 'simulated')},
            'status': 'abnormal' if bad else 'normal', 'method': 'demo_threshold_rule'}
def step(client, state):
    for machine in c.MACHINES:
        for sample in client.records(c.telemetry(machine)):
            key = machine+':'+sample['sample_id']
            if state.has(key):
                continue
            result = analyze(sample)
            client.put(c.MN_BASE+'/analyzer/results', result)
            state.mark(key)
            print('ANALYZED', machine, result['status'], sample['sample_id'], flush=True)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--once', action='store_true')
    a = p.parse_args()
    c.require_mn()
    client, state = Client(c.MN_URL), State('analyzer')
    while True:
        try:
            step(client, state)
        except Exception:
            if a.once:
                raise
            logging.exception('Analysis failed; retrying')
        if a.once:
            return
        time.sleep(max(c.POLL_SECONDS, 0.1))
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
