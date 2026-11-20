# Per-Machine Isolation Forest Analysis

Inputs are temperature °C, vibration RMS mm/s, and current A. Each collector ID + machine ID
has a separate model. ML requires exactly one value for each input sensor type.
Other sensors remain registered but are excluded from ML inputs.
The model uses three current values; time-window averages and changes have not been added.

## Execution
Activate the existing runtime environment and load session.env from the repository root.

```bash
pip install -r apps/requirements.txt
python apps/ml_manage.py generate --dataset ml_data/normal.json --seed 42
python apps/ml_manage.py train --dataset ml_data/normal.json
python apps/ml_manage.py generate-test --dataset ml_data/test.json --seed 123
python apps/ml_manage.py evaluate --dataset ml_data/test.json
python apps/collector_ae.py --help
python apps/analyzer_ae.py
```

The generator creates normal operating patterns for machine-01 and machine-02 beneath
collector-01 or QF_COLLECTOR_ID. For other IDs, change --collector-id or the generator profiles.
The test file above can be replayed through the collector's existing --dataset argument.
Training uses 80% of normal data; the remaining 20% calibrates the 99th-percentile anomaly-score threshold.
The 100-sample-per-machine minimum is for demonstration execution, not a sufficient real-equipment dataset.
Generate test data with a different seed/run. generate-test includes normal operation, sudden multivariate changes,
gradual increases, and recovery. Labels come from the scenario, not existing threshold rules.
Shutdown and startup are outside the current training scope.

## Operation
- QF_ML_MODEL_DIR: model directory; defaults to QF_STATE_DIR/ml_models.
- QF_ML_CONSECUTIVE: consecutive anomalous samples; defaults to 3. Actual latency depends on transmission intervals.
- Machines without models show collecting_baseline and retain threshold monitoring.
  This indicates preparation is required; live data is not automatically collected or used for training.
- Training runs only through the train command. Explicitly supply data confirmed to be normal.
- Models are saved atomically and changed files are loaded from the next sample. Use joblib only with trusted
  locally trained files. Retrain when the scikit-learn version changes.
- ML classifies the machine's combined sensor inputs. Individual sensor status retains threshold-based rules;
  current is unassessed because it has no individual threshold. The score is not a failure probability.
- Existing temperature/vibration threshold alarms remain immediate at 75°C or 7 mm/s. ML-only anomalies
  become abnormal after 3 consecutive samples. Normal/missing-input/no-model states reset the count.
- Completed samples are not reanalyzed. Send new samples after applying a model.
  Delivery retries reuse saved results and do not increase the count for the same sample.

## Validation and Limitations
The evaluation tool reports per-machine TP/FP/TN/FN, detection rate, and false-positive rate for raw ML
results and existing thresholds. These are not end-to-end metrics including consecutive alerts and network latency.
Unit tests check consecutive alerts, recovery, model reloading, ID isolation, unregistered machines, and input
validation. In real operation, record alert times and anomaly onset separately to measure delay.
Single-sensor anomalies may be missed more often than anomalies across sensor combinations; different detection
rates were also observed in testing. Synthetic-data performance does not establish real-equipment performance or failure prediction.
