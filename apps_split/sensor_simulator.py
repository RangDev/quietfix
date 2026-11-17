"""JSON dataset adapter; no server, network request, or background thread."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from device_model import normalize
class SensorSimulator:
    def __init__(self, dataset, replay_id='default', collector_id='collector-01'):
        raw = Path(dataset).read_bytes()
        self.records = json.loads(raw)
        if not isinstance(self.records, list) or not self.records:
            raise ValueError('Dataset must be a nonempty JSON array')
        self.fingerprint = hashlib.sha256(raw).hexdigest()
        self.replay_id = replay_id
        self.collector_id = collector_id
        for i, row in enumerate(self.records):
            try:
                if not isinstance(row, dict):
                    raise ValueError('Row must be an object')
                self.records[i] = normalize(row)
            except ValueError as e:
                raise ValueError(f'Row {i}: {e}') from e
    def __len__(self):
        return len(self.records)
    def read_measurements(self, index):
        """index is the absolute sequence number, not just the JSON row number."""
        if index < 0:
            raise ValueError('index must be nonnegative')
        cycle, row_index = divmod(index, len(self.records))
        row = dict(self.records[row_index])
        row['sample_id'] = hashlib.sha256(
            f'v3:{self.collector_id}:{self.fingerprint}:{self.replay_id}:{index}'.encode()).hexdigest()
        row['collector_id'] = self.collector_id
        row['source_sample_id'] = self.records[row_index].get('sample_id')
        # Ignore any preset timestamp. Collector calls this immediately before sending.
        row['timestamp'] = datetime.now(timezone.utc).isoformat()
        row['dataset_index'] = row_index
        row['cycle'] = cycle + 1
        row['sequence'] = index
        row['replay_id'] = self.replay_id
        row['simulated'] = True
        return row
