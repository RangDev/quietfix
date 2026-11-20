"""Per-collector, per-machine Isolation Forest; never trains on live traffic."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest
from device_model import normalize, identifier

FEATURES = [('temperature', '°C'), ('vibration_rms', 'mm/s'), ('current', 'A')]

def vector(sample):
    sensors = normalize(sample)['sensors']
    values = []
    for kind, unit in FEATURES:
        matches = [s for s in sensors if s['type'] == kind and s['unit'] == unit]
        if len(matches) != 1:
            raise ValueError(f'Exactly one {kind} sensor in {unit} is required')
        values.append(matches[0]['value'])
    return values

def identity(sample):
    return identifier(sample['collector_id']), identifier(sample['machine_id'])

def model_path(directory, key):
    return Path(directory) / (hashlib.sha256(json.dumps(key).encode()).hexdigest()+'.joblib')

def train(rows, directory):
    groups = {}
    for row in rows:
        if row.get('label') != 'normal':
            raise ValueError('Training rows must be explicitly labeled normal')
        groups.setdefault(identity(row), []).append(vector(row))
    bundles = []
    for key, values in groups.items():
        if len(values) < 100:
            raise ValueError(f'{key}: at least 100 normal rows required (demo minimum)')
        # Separate fit and calibration blocks; final test data are supplied separately.
        cut = int(len(values)*.8)
        model = IsolationForest(n_estimators=100, contamination='auto', random_state=42).fit(values[:cut])
        threshold = float(np.quantile(-model.score_samples(values[cut:]), .99))
        digest = hashlib.sha256(json.dumps(values).encode()).hexdigest()
        bundles.append((key, dict(model=model, threshold=threshold, key=key,
                        features=FEATURES, sklearn=sklearn.__version__, version=digest,
                        source='synthetic' if all(r.get('simulated') for r in rows) else 'provided',
                        fit_count=cut, calibration_count=len(values)-cut)))
    if not bundles:
        raise ValueError('Empty training dataset')
    Path(directory).mkdir(parents=True, exist_ok=True)
    for key, bundle in bundles:
        target = model_path(directory, key)
        temp = target.with_suffix('.tmp')
        joblib.dump(bundle, temp)
        temp.replace(target)
    return len(bundles)

class Models:
    def __init__(self, directory):
        self.directory = directory
        self.cache = {}

    def predict(self, sample):
        key = identity(sample)
        path = model_path(self.directory, key)
        if not path.exists():
            return {'model_state': 'collecting_baseline', 'is_outlier': False}
        stamp = path.stat().st_mtime_ns
        if key not in self.cache or self.cache[key][0] != stamp:
            # Only load locally trained/trusted artifacts. joblib is executable serialization.
            bundle = joblib.load(path)
            if (tuple(bundle['key']) != key or bundle['features'] != FEATURES
                    or bundle['sklearn'] != sklearn.__version__):
                raise ValueError('Model identity/schema/library version mismatch; retrain')
            self.cache[key] = stamp, bundle
        bundle = self.cache[key][1]
        try:
            values = vector(sample)
        except ValueError as error:
            return {'model_state': 'invalid_input', 'is_outlier': False, 'detail': str(error)}
        score = float(-bundle['model'].score_samples([values])[0])
        return {'model_state': 'ready', 'is_outlier': score > bundle['threshold'],
                'anomaly_score': score, 'threshold': bundle['threshold'],
                'model_version': bundle['version'], 'training_source': bundle['source']}
