# Deployment and Operation

## Supported Scope

The supported configuration is Linux, Python 3.12, and single-host loopback HTTP. Ubuntu 24.04 is
the deployment target. Validation environments and results are recorded in [VALIDATION.md](VALIDATION.md).
ACME 2025.11 and direct application dependencies are pinned in requirements files.
The complete dependency set used for Linux/Python 3.12 validation is in standalone/requirements-lock.txt.
Recreate moved virtual environments and check resourcesPath in CSE configuration.
On Windows, run inside an Ubuntu VM or WSL.

## Initial Installation

```bash
git clone --branch main --single-branch https://github.com/RangDev/quietfix.git
cd quietfix
python3 -m venv .venv
.venv/bin/python -m pip install -r standalone/requirements-lock.txt
.venv/bin/python standalone/manage.py prepare
source runtime/standalone/session.env
```

Private repositories require Git authentication first. If Ubuntu lacks the venv module,
install it with `sudo apt install python3-venv`. The prepare command above preserves existing environment
and CSE configuration files. It does not delete or automatically migrate existing data.

## ML Training and Independent Evaluation

```bash
.venv/bin/python apps/ml_manage.py generate --dataset ml_data/normal.json --seed 42
.venv/bin/python apps/ml_manage.py train --dataset ml_data/normal.json
.venv/bin/python apps/ml_manage.py generate-test --dataset ml_data/test.json --seed 123
.venv/bin/python apps/ml_manage.py evaluate --dataset ml_data/test.json
```

The default generator trains only machine-01 and machine-02 under collector-01.
It uses 80% normal data for training, 20% for threshold calibration, and a different seed for testing.
Live readings are not automatically treated as normal training data. For actual equipment, provide data
confirmed to be normal under the corresponding IDs and explicitly run train.

## Execution: Two Demonstrations

### Basic Eight-Machine Monitoring

```bash
.venv/bin/python standalone/service.py start
```

The default timeline displays eight machines. Only trained machine-01 and machine-02 have ready models;
the other six retain threshold monitoring without models. The basic eight-machine data distribution
differs from training data and cannot be used to evaluate ML accuracy.

### Two-Machine ML Demonstration Matching Training

Stop any running services first.

```bash
.venv/bin/python standalone/service.py stop
.venv/bin/python standalone/service.py start --dataset ml_data/test.json --interval 1 --replay-id ml-demo01
```

The default 1,000 test points per machine produce 2,000 rows for two machines, taking about 33 minutes per replay.
Raw ML results move through normal operation, abrupt combined changes, gradual changes, and recovery. Runtime
alerts require 3 consecutive anomalies, so they differ from evaluate metrics. To shorten the demonstration,
create a separate file with `generate-test --count 100` and run it with a new replay-id.
The same file/replay-id resumes transmission after restart.

## Status, Logs, Shutdown, and Restart

```bash
.venv/bin/python standalone/service.py status
.venv/bin/python standalone/service.py logs --service analyzer
.venv/bin/python standalone/service.py logs --service backup
.venv/bin/python standalone/service.py stop
.venv/bin/python standalone/service.py start
```

The manager starts IN → MN → resource setup → analyzer → backup → dashboard → collector.
If startup fails, it cleans up processes started during that attempt. stop shuts them down in reverse order.
status checks process liveness and does not replace data-path verification.
Duplicate starts and occupied ports are rejected. Automatic restart and startup after reboot are not provided.
Manually launched services are not managed and must be stopped in their own terminals.

Dashboard: http://127.0.0.1:8090/ · API: http://127.0.0.1:8090/api
Check that machines[].analysis.ml.model_state is ready and source/result sample_id values
match. Inspect logs if the API reports error or waiting_for_analysis.
Successful start confirms HTTP readiness, not completed ML analysis for every machine.

| Item | Default Location/Port |
|---|---|
| IN-CSE | 127.0.0.1:9090, quietfix-in |
| MN-CSE | 127.0.0.1:8081, quietfix-mn |
| Dashboard | 127.0.0.1:8090 |
| Analyzer/backup notifications | 8091 / 8092 |
| Environment file | runtime/standalone/session.env |
| CSE configuration/databases | runtime/standalone/in and mn |
| AE checkpoints | runtime/standalone/state |
| Trained models | state/ml_models beneath the path above |
| Service logs | runtime/standalone/logs |

The manager assumes default local ports and CSE names. For custom ports, distributed equipment,
MQTT, TLS, ACP, and transfer experiments, follow the [manual operation guide](../standalone/README.md) and feature documentation.
It reads simple export KEY=value entries in session.env without evaluating shell commands.

## Validation and Preservation

Stop all services before running:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python standalone/smoke_test.py
```

The smoke test uses temporary databases to verify actual IN/MN, Mcc, eight-machine storage/analysis/central copies,
and API snapshots. Manager execution and trained-model application have [separate validation records](VALIDATION.md).
Skipped optional browser/TLS tests do not count as passes.

After shutdown, copy all of runtime/standalone to preserve CSE databases, state, models, and environment files.
Reuse the same location and virtual environment when restarting. On another host, check
addresses and resourcesPath; do not reuse services.json because it records process state.
Use SSH port forwarding to access the VM externally. The default CAdmin/HTTP configuration is not intended for public exposure.
