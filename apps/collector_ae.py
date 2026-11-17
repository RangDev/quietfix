"""Read the dataset sequentially and publish to MN-CSE. No dashboard or AI."""
import argparse
import logging
import math
import time
import config as c
from onem2m_client import Client
from sensor_simulator import SensorSimulator
from worker_state import State
from device_model import identifier
from resource_registry import ensure_ae, publish

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', default=str(c.ROOT/'test_data.json'))
    p.add_argument('--replay-id', default='default')
    p.add_argument('--interval', type=float, default=5)
    p.add_argument('--cycles', type=int, default=0, help='0: repeat forever; N: stop after N total cycles')
    a = p.parse_args()
    if not math.isfinite(a.interval) or a.interval < 0:
        p.error('--interval must be finite and nonnegative')
    if a.cycles < 0:
        p.error('--cycles must be nonnegative')
    c.require_mn()
    identifier(c.COLLECTOR_ID)
    sensor = SensorSimulator(a.dataset, a.replay_id, c.COLLECTOR_ID)
    state = State('collector-'+c.COLLECTOR_ID)
    key = 'v3:'+c.COLLECTOR_ID+':'+sensor.fingerprint+':'+a.replay_id
    index = state.position(key)
    client = Client(c.MN_URL)
    # AE registration is performed at startup, before the first measurement.
    while True:
        try:
            ensure_ae(client, c.MN_BASE, c.COLLECTOR_ID)
            break
        except Exception:
            logging.exception('AE registration failed; retrying')
            time.sleep(max(c.POLL_SECONDS, 0.1))
    deadline = time.monotonic()
    while a.cycles == 0 or index < len(sensor) * a.cycles:
        time.sleep(max(0, deadline - time.monotonic()))
        sample = state.pending_sample(key)
        if sample is None:
            sample = sensor.read_measurements(index)
            state.save_pending(key, sample)
        started = time.monotonic()
        try:
            publish(client, sample)
            state.complete(key, index+1)
        except Exception:
            logging.exception('Publish failed; retrying row %s', index)
            time.sleep(max(c.POLL_SECONDS, 0.1))
            continue
        print(f"SENT row={sample['dataset_index']+1}/{len(sensor)} cycle={sample['cycle']} timestamp={sample['timestamp']} machine={sample['machine_id']} sample_id={sample['sample_id']}", flush=True)
        index += 1
        deadline = started + a.interval
    print('Dataset complete. Use a new --replay-id to replay.', flush=True)
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
