"""Independent analysis AE: consume MN telemetry and persist machine-specific ML and threshold results."""
import argparse
import config as c
from onem2m_client import Client
from worker_state import State
from event_worker import run
from device_model import normalize, sensor_status, machine_status
from resource_registry import discover_machines, ensure_analyzer

def analyze(sample, models=None, previous_streak=0):
    sensors = [{**s, 'status': sensor_status(s)} for s in normalize(sample)['sensors']]
    statuses = {s['status'] for s in sensors}
    status = machine_status(sensors)
    from ml_anomaly import Models
    prediction = (models or Models(c.ML_MODEL_DIR)).predict(sample)
    streak = previous_streak + 1 if prediction['is_outlier'] else 0
    rule_status = status
    if streak >= c.ML_CONSECUTIVE:
        status = 'abnormal'
    return {**{k: sample[k] for k in ('sample_id', 'collector_id', 'machine_id', 'timestamp', 'simulated')},
            'status': status, 'method': 'isolation_forest_with_threshold_rules', 'sensors': sensors,
            'rule_status': rule_status, 'ml': {**prediction, 'consecutive': streak,
                'required_consecutive': c.ML_CONSECUTIVE,
                'status': 'abnormal' if streak >= c.ML_CONSECUTIVE else
                          'pending' if prediction['is_outlier'] else
                          'normal' if prediction['model_state'] == 'ready' else 'unassessed'},
            'coverage': 'partial' if 'unassessed' in statuses else 'complete'}

from routing import guarded

@guarded
def step(client, state, models=None):
    results = ensure_analyzer(client)
    for machine in discover_machines(client, c.MN_BASE):
        for sample in sorted(client.records(machine['path']+'/telemetry'),
                             key=lambda row: (row.get('timestamp', ''), row.get('sequence', 0))):
            key = 'v3:'+machine['collector_id']+':'+machine['machine_id']+':'+sample['sample_id']
            if state.has(key):
                continue
            if c.FLEX_ENABLED:
                from flex_model import with_typed_readings
                sample = with_typed_readings(sample, machine)
            streak_key = 'ml-streak:'+machine['collector_id']+':'+machine['machine_id']
            pending = state.pending_sample(key)
            if pending is None:
                result = analyze(sample, models, state.position(streak_key))
                pending = {'result': result}
                state.save_pending(key, pending)
            result = pending['result']
            client.put(results, result)
            state.advance(streak_key, result['ml']['consecutive'])
            state.mark(key)
            state.complete(key, 0)
            print('ANALYZED', machine['machine_id'], result['status'], sample['sample_id'], flush=True)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--once', action='store_true')
    a = p.parse_args()
    c.require_mn()
    client, state = Client(c.MN_URL, c.role_origin('analyzer')), State('analyzer')
    from ml_anomaly import Models
    models = Models(c.ML_MODEL_DIR)
    run('analyzer', client, lambda: step(client, state, models), a.once)
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
