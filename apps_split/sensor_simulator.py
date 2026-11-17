"""JSON dataset adapter; no server, network request, or background thread."""
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from config import MACHINES
FIELDS = ('temperature_c', 'vibration_rms_mm_s', 'current_a')
class SensorSimulator:
    def __init__(self, dataset, replay_id='default'):
        raw = Path(dataset).read_bytes()
        self.records = json.loads(raw)
        if not isinstance(self.records, list) or not self.records:
            raise ValueError('Dataset must be a nonempty JSON array')
        self.fingerprint = hashlib.sha256(raw).hexdigest()
        self.replay_id = replay_id
        for i, row in enumerate(self.records):
            if not isinstance(row, dict) or row.get('machine_id') not in MACHINES:
                raise ValueError(f'Row {i}: invalid machine_id')
            for key in FIELDS:
                v = row.get(key)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                    raise ValueError(f'Row {i}: {key} must be a finite number')
    def __len__(self):
        return len(self.records)
    def read_measurements(self, index):
        """index is the absolute sequence number, not just the JSON row number."""
        if index < 0:
            raise ValueError('index must be nonnegative')
        cycle, row_index = divmod(index, len(self.records))
        row = dict(self.records[row_index])
        row['sample_id'] = hashlib.sha256(
            f'v2:{self.fingerprint}:{self.replay_id}:{index}'.encode()).hexdigest()
        row['source_sample_id'] = self.records[row_index].get('sample_id')
        # Ignore any preset timestamp. Collector calls this immediately before sending.
        row['timestamp'] = datetime.now(timezone.utc).isoformat()
        row['dataset_index'] = row_index
        row['cycle'] = cycle + 1
        row['sequence'] = index
        row['replay_id'] = self.replay_id
        row['simulated'] = True
        return row
