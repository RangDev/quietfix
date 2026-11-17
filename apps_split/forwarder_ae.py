"""Copy retained MN telemetry/results into IN archive; no analysis or UI."""
import argparse
import logging
import time
import config as c
from onem2m_client import Client
from worker_state import State

def step(mn, central, state):
    paths = [(c.telemetry(m), f'{c.IN_BASE}/archive/{m}') for m in c.MACHINES]
    paths.append((c.MN_BASE+'/analyzer/results', c.IN_BASE+'/archive/results'))
    for source, target in paths:
        for sample in mn.records(source):
            key = source+':'+sample['sample_id']
            if state.has(key):
                continue
            central.put(target, sample)
            state.mark(key)
            print('FORWARDED', target, sample['sample_id'], flush=True)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--once', action='store_true')
    a = p.parse_args()
    c.require_mn()
    mn, central, state = Client(c.MN_URL), Client(c.IN_URL), State('forwarder')
    while True:
        try:
            step(mn, central, state)
        except Exception:
            if a.once:
                raise
            logging.exception('Forwarding failed; retrying')
        if a.once:
            return
        time.sleep(max(c.POLL_SECONDS, 0.1))
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
