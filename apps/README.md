# QuietFix Split Applications · Dynamic Machine/Sensor Registration

For initial installation, training, and service execution, follow the [deployment guide](../docs/DEPLOYMENT.md). Analysis combines per-machine Isolation Forest with existing thresholds. See the [ML guide](ML.md).

One collector manages multiple machines, each with multiple sensors. Standalone ACME MN-CSE/IN-CSE instances provide CSE services. Follow the [standalone guide](../standalone/README.md) for server execution. This application code does not replace a CSE server.

## Registration and Data Flow

| Trigger | Component and Action |
|---|---|
| Collector startup | Registers an AE named `QF_COLLECTOR_ID` on MN; reuses it if it already exists |
| First reading from a new machine | Collector automatically creates the machine container, telemetry, and metadata beneath its AE |
| First reading from a new sensor | Adds sensor ID, type, display name, and unit to machine metadata |
| Analyzer polling | Discovers MN resources labeled `quietfix-machine-v3` and analyzes samples from all discovered machines |
| Backup management AE polling | Copies machine/sensor lists and raw data to IN, creating storage resources automatically |
| Dashboard polling | Discovers machines on IN and builds machine cards and sensor rows automatically |

No code changes or fixed lists are required for each machine/sensor. Sensors are not AEs; machines are represented as containers. Physical USB/wireless discovery and drivers are not included. Currently, `machine_id` and `sensors` read by the JSON adapter simulate device recognition.

## Resource Paths

The default collector ID is `collector-01`. Machine container names include a `machine-` prefix to avoid collisions with legacy resources.

| Location | Example Resource |
|---|---|
| MN collector AE | `<MN_BASE>/collector-01` |
| MN machine container | `<MN_BASE>/collector-01/machine-machine-03` |
| MN raw CIN | Beneath `telemetry` in the machine container |
| MN sensor-list CIN | Beneath `metadata` in the machine container |
| MN analysis-result CIN | Beneath `<MN_BASE>/analyzer/results` |
| IN source/list | `<IN_BASE>/archive/collector-01/machine-machine-03/{telemetry,metadata}` |
| IN analysis-result CIN | Beneath `<IN_BASE>/archive/results` |

IN paths also include collector IDs to distinguish identical machine IDs belonging to different collectors. Analysis and alerts are linked by `(collector_id, machine_id, sample_id)`. Moving a machine to another collector is treated as a separate registration.

New telemetry/results containers each retain up to 1,000 CINs; metadata retains only the latest one. Existing container settings are not overwritten. Sensor lists merge previously registered sensors and do not delete them automatically.

## Updating and Running

The directory was renamed from `apps_split` to `apps`. If using the default state path, stop all applications, update Git, and move any remaining `apps_split/state/` to `apps/state/` to resume progress. Do not overwrite an existing target state directory. Keep an explicitly configured `QF_STATE_DIR` unchanged. Update service/script execution paths to `apps/` too.

Stop the existing four split applications (collector, analyzer, backup management AE, dashboard) with Ctrl+C and update the repository. Do not run the old combined version simultaneously. Keep existing CSEs running.

```bash
git pull --ff-only
source session.env
export QF_COLLECTOR_ID=collector-01
.venv/bin/python -m pip install -r apps/requirements.txt
# Optional: prepare shared resources in advance. Each application also creates required resources automatically.
.venv/bin/python apps/setup_resources.py
```

In each terminal, enter the repository directory, run `source session.env`, then run one command below. For a nondefault collector ID, set it in that terminal, for example `export QF_COLLECTOR_ID=gateway-west`.

```bash
.venv/bin/python apps/analyzer_ae.py
.venv/bin/python apps/backup_ae.py
.venv/bin/python apps/dashboard.py
.venv/bin/python apps/collector_ae.py --dataset test_data/test_data_expanded.json --interval 5 --replay-id dynamic01
```

Dashboard: http://127.0.0.1:8090/ (`/api` provides JSON for programs).

`test_data_expanded.json` contains machines 1/2, new machine 3, a pressure sensor added later to machine 3, and pressure-only machine 4. Machine 3 changes from an anomalous four-sensor state to a recovered five-sensor state. Machine 4 remains unassessed. Since the list repeats, samples preceding sensor addition may show pressure as “Missing from this sample”.

Use `--cycles 1` for one pass, or a new `--replay-id` to resend the same dataset from the beginning. The same ID/file resumes from its checkpoint after restart. The default repeats indefinitely and generates UTC timestamps immediately before transmission. Failed rows retry with the same ID and timestamp.

JSON files are read at collector startup. After adding machines/sensors, **restart only the collector**. The analyzer, backup management AE, and dashboard discover updates on their next poll without restarting. Real drivers should pass samples in the same format to `resource_registry.publish(client, sample)`.

## JSON Format

Legacy `test_data.json` fields `temperature_c`, `vibration_rms_mm_s`, and `current_a` remain supported. Use the following format for new sensors or multiple sensors of the same type.

```json
[
  {
    "machine_id": "machine-03",
    "machine_name": "Machine 3",
    "sensors": [
      {"sensor_id": "motor-temp", "type": "temperature", "label": "Motor Temperature", "value": 65, "unit": "°C"},
      {"sensor_id": "bearing-temp", "type": "temperature", "label": "Bearing Temperature", "value": 78, "unit": "°C"},
      {"sensor_id": "pressure", "type": "pressure", "label": "Pressure", "value": 2.4, "unit": "bar"}
    ]
  }
]
```

Each row is **one machine's current sensor snapshot**, not one sensor event per row. IDs are 1–64 letters, digits, `-`, or `_`, beginning with a letter/digit. Sensor IDs must be unique within a machine. Values must be finite numbers. When `sensors` exists, it replaces legacy flat fields. The collector generates `collector_id`, `sample_id`, `timestamp`, and `simulated`.

A registered sensor absent from the current snapshot shows value `—` and “Missing from this sample”. Previous readings are not reused as current values. Use a new sensor ID when changing a sensor's type or unit.

## Analysis and Display

| Sensor Type / Unit | Classification |
|---|---|
| `temperature` / `°C` | abnormal at or above 75 |
| `vibration_rms` / `mm/s` | abnormal at or above 7 |
| Other types or units | unassessed; still stored, copied, and displayed |

Same-type sensors on a machine are classified separately. Any anomaly makes the machine ABNORMAL; all assessable sensors normal makes it NORMAL. Unassessed sensors are indicated separately; if none can be assessed, the machine is unassessed. No arbitrary current/pressure thresholds were added. See the [ML guide](ML.md) for per-machine Isolation Forest classification.

The card UI, current clock, red anomaly border, and maximum of 10 alerts remain. Alerts also include collector and anomalous sensor names. The same analysis sample is not duplicated. Alerts use server memory; after restart, recent alerts are reconstructed from retained IN results. Dashboard polling is every 3 seconds; analysis/backup polling defaults to 2 seconds, so updates are not simultaneous.

## Compatibility and State Files

Existing `<MN_BASE>/collector-01/telemetry`, `collector-02/telemetry`, and direct IN machine containers are not deleted. New applications process/display only labeled v3 machines and **do not automatically migrate legacy source data**. New collectors write to new paths. Old anomaly history in shared results may appear as legacy alerts.

Collector state is stored in `state/collector-<collectorID>.sqlite3`; sample/checkpoint keys are namespaced as v3. The first upgraded run therefore sends existing datasets from the beginning. The analyzer and backup management AE reuse existing SQLite files with v3 keys. Do not commit `.venv`, `session.env`, `state/`, or runtime databases. If CSE databases are reset, stop applications and use a new `QF_STATE_DIR` and replay-id.

Use distinct `QF_COLLECTOR_ID` values for multiple collectors. Never run multiple processes with the same collector ID simultaneously. Production deployments require per-application permissions/ACP and authentication; the current CAdmin configuration is for development. Collector/backup management AEs need resource-creation rights; analyzer/dashboard need discovery/retrieval rights for registered resources.

## Validation and Limitations

```bash
python3 -m unittest discover -s tests -v
```

A local HTTP oneM2M test server verifies registration → analysis → IN forwarding → dashboard API construction. This does not replace actual ACME/physical-sensor integration tests. Validation scope is recorded in `VALIDATION.txt`. This is a small polling prototype: the 10,000-resource discovery limit and CSE retention can cause unprocessed data loss. Long-term/high-volume operation, deregistration, individual sensor events, and hot reload are outside scope.

## File Responsibilities

| File | Responsibility |
|---|---|
| `collector_ae.py` / `sensor_simulator.py` | Collector AE registration, JSON input, machine/sensor registration, delivery |
| `device_model.py` | Sensor schema validation, legacy-format conversion, sensor classification rules |
| `resource_registry.py` | AE/container setup, machine/sensor lists, dynamic discovery |
| `analyzer_ae.py` | Registered-machine retrieval and per-sample analysis |
| `backup_ae.py` | Copies machine/sensor lists, readings, and analysis results to IN |
| `dashboard.py` | IN-only queries, dynamic cards/sensor rows, alerts |
| `onem2m_client.py` | Shared HTTP and oneM2M requests |
| `worker_state.py` | Local progress and pending deliveries in SQLite |
| `setup_resources.py` | Optional shared-resource initialization |

## Subscriptions, Notifications, and Group Latest-Value Queries

HTTP notifications can wake the analyzer and backup management AE to process retained pending samples. Notifications trigger processing; data is retrieved from the CSE. Existing SQLite deduplication remains, with full reconciliation every 30 seconds to process retained data after missed notifications. Deleted data cannot be recovered. New-machine discovery/subscription creation also runs during reconciliation; samples received before subscription are handled by retrieval.

Set a **VM address reachable from the MN-CSE container** in `session.env`. Replace VM_IP below with the actual address.

```bash
export QF_ANALYZER_NOTIFY_URL=http://VM_IP:8091/notify
export QF_FORWARDER_NOTIFY_URL=http://VM_IP:8092/notify
export QF_RECONCILE_SECONDS=30
```

Reload the environment in each terminal and restart analyzer/backup management AE with existing commands. Default bind address is 0.0.0.0; ports are 8091/8092. Change both `QF_ANALYZER_NOTIFY_PORT`/`QF_FORWARDER_NOTIFY_PORT` and URLs when changing ports. 127.0.0.1 inside MN does not refer to host applications. Ports must be reachable and subscription creation permitted. Receivers start before subscription creation and answer CSE verification notifications. URL changes apply at the next subscription check.

Without URLs, applications log a warning and use existing `QF_POLL_SECONDS` polling. If a configured subscription fails, they log the error and continue 30-second reconciliation. `--once` performs one pass without a receiver or subscriptions. Run one process per role in notification mode. Expose notification ports only on trusted development networks.

The analyzer subscribes to each machine's telemetry; backup management subscribes to telemetry and MN analyzer/results. Backup management automatically creates/updates IN `archive/telemetryGroup` (ty=9) with all machine telemetry containers as members. The dashboard retrieves latest CINs using `GET <IN_BASE>/archive/telemetryGroup/fopt/la`. Missing groups or empty members fall back to individual machine queries. Sensor results attach only to matching sample_id values; machine status retains the last analysis. Group queries do not replace workers' all-sample processing. Dashboard refresh remains 3 seconds.

Backup management owns the group; the dashboard only reads IN. Internally, the CSE requests each member separately, without guaranteeing a shared timestamp or atomic snapshot. Group creation/update errors are logged while data copying continues. This uses HTTP without a separate database or MQTT broker.

## Per-Machine Adaptive Collection (v4 · Default)

Default execution measures every active machine separately each second instead of waiting per JSON row. Normal/unassessed states enqueue every 5 seconds; ongoing anomalies enqueue every second. First measurements, anomaly onset, recovery, and other status changes enqueue immediately after measurement. “Immediately” means recognition within the measurement interval and queueing, not guaranteed delivery during network delay/outages. Value changes within the same status wait for the next normal periodic transmission.

```bash
source session.env
.venv/bin/python apps/collector_ae.py --replay-id adaptive01
# Default dataset: test_data/test_data_timeline.json
# Adjustment example:
.venv/bin/python apps/collector_ae.py --mode adaptive --replay-id adaptive02 \
  --measure-period 1 --normal-period 5 --abnormal-period 1
```

Environment defaults are QF_MEASURE_PERIOD=1, QF_NORMAL_PERIOD=5, QF_ABNORMAL_PERIOD=1. CLI values take precedence. One second is the interval for reading calculated temperature/RMS values, not raw vibration/AC waveform sampling. Real drivers must implement appropriate bandwidth-specific sampling. Collector and analyzer share device_model.py rules; analyzer results still determine dashboard classification.

Timed JSON contains duration_seconds and a frames array. Each frame specifies at_seconds and a machine sensor snapshot, held until the next frame. Machines appear at their first frame. The default file starts eight machines at 0 seconds: 1–4 in Zone A, 5–8 in Zone B. Machine 9 automatically registers at 120 seconds under Unassigned. At 30/90/150/210/270 seconds, only machine 3/6/9/4/8 respectively becomes anomalous, recovering 15 seconds later; the cycle repeats every 300 seconds. The earlier delayed-appearance scenario remains in test_data/test_data_dynamic_timeline.json. Machines not yet present in a new cycle produce no new readings, while prior CSE/dashboard values remain. --cycles 1 measures one cycle, drains the outbox, and exits. A disconnected collector waits for recovery and can be stopped with Ctrl+C.

Elapsed time follows persisted measurement ticks and resumes at the interrupted scenario position. The scenario does not advance while stopped. Changing file/replay-id/interval settings starts separate progress. Scheduling uses a monotonic clock and does not generate bursts of historical measurements after local delays. Exact one-second timing is not guaranteed for large machine counts or slow disks.

Legacy array JSON remains supported in sequential replay mode. Supplying --interval also selects sequential replay. Earlier --interval examples remain sequential; use the commands above for adaptive testing.

```bash
.venv/bin/python apps/collector_ae.py --mode replay --dataset test_data/test_data_expanded.json --interval 5
```

The measurement loop and HTTP delivery thread are independent and use separate SQLite connections. state/adaptive-<collectorID>.sqlite3 atomically stores scenario progress and a FIFO outbox. Samples are removed only after server acknowledgement. Retries preserve sample_id, measurement time, and first delivery attempt, enabling existing CIN deduplication. Stop applications before moving databases to account for WAL files. Run one process per collector ID. Sequential-replay checkpoints do not automatically migrate to adaptive mode.

The default outbox limit is QF_OUTBOX_LIMIT=10000. A full outbox rejects new samples rather than overwriting pending data; errors and the schedule's cumulative dropped counter record this. Measurements continue, so transient anomaly/recovery events may be lost. Intervals follow enqueue time rather than successful delivery, limiting generation during outages. FIFO recovery can display historical samples first. A failed head sample delays later deliveries.

The dashboard shows measurement time, first delivery attempt, and delivery reason. First attempt is not CSE reception time. Last received values remain between normal transmissions; refresh remains 3 seconds. This version does not add automatic stale/offline health classification or UI reception-delay alerts.

## Optional Role-Based ACP

Default settings preserve the development/dataset workflow. After applying CSE permissions, `QF_ACP_ENABLED=1` selects per-application Originators and restrictive ACPs. See [ACP.md](ACP.md) for setup, live validation, restoration, and security scope. New gateway AEs require administrator provisioning; machines beneath registered gateways register automatically.

## Optional FlexContainer Model

`QF_FLEX_ENABLED=1` creates models with explicit sensor types/units/values and uses FCNT query-based discovery. Install models on both CSEs and reapply ACPs. See [FLEX.md](FLEX.md) for setup, validation, and transition procedures.

## Optional Collector MQTT Binding

`QF_COLLECTOR_PROTOCOL=mqtt` enables oneM2M MQTT only between collector and MN-CSE. AE provisioning, ACP mode, a broker, and ACME MQTT settings are required. See [MQTT.md](MQTT.md) for architecture, validation, and execution. Default HTTP behavior and other applications' HTTP communication remain.

## Authenticated transport, semantic discovery and controlled transfer

- [Authenticated HTTPS/MQTTS and Originator/topic binding](../security/README.md)
- [SAREF descriptors and explicit unit mapping](SEMANTICS.md)
- [Controlled MN-CSE transfer and retained-state restoration](HANDOVER.md)

These features require separate configuration.

## Dashboard by Zone

Machine cards show statuses such as normal/anomaly; sensor values and attributes appear in the selected machine's detail panel. Manage zone assignments through dashboard_sections.json or QF_DASHBOARD_SECTIONS without changing sensor JSON. See the [dashboard guide](DASHBOARD.md).


## Backup Path in the oneM2M-Only Implementation

`backup_ae.py` runs on the MN device and reads source measurements and analysis results from MN. It sends IN-copy requests to `~/IN-CSE-ID/IN-CSEBase/...` at the MN URL. MN forwards over Mcc, so there is no direct Mca link between backup AE and IN. Analysis and backup AEs are separate programs. See the [standalone guide](../standalone/README.md) for initial permissions and custom CSE-IDs. The previous `forwarder_ae.py` command invokes the same backup implementation and reuses existing identities, subscriptions, and SQLite state.

