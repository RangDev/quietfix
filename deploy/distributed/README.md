# Distributed deployment

Copy collector/, field/, and central/ to their respective Linux/Python 3.12 devices.
Each node directory contains its own source and dependencies; keep its entire contents.
Shared application modules are intentionally included in every node to support optional
features without importing the source repository. Only the selected role's programs run.

This profile uses HTTP/CAdmin on a trusted private test network. It is not a hardened
Internet deployment. Use the included security examples and configure authenticated TLS
before exposing services beyond that network. MQTT and cross-host handover are outside
this deployment profile. Sensors are simulated; physical sensor drivers are separate work.

## Configure every node

Run inside each copied node directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp node.env.example node.env
```

Edit node.env on all nodes: replace 192.168.10.20 with the field server's reachable address
and 192.168.10.30 with the central server's reachable address. Keep CSE IDs/bases identical
across nodes. Bind addresses control listening; URLs advertise reachable addresses.
Callbacks remain loopback because analyzer/backup and MN run on the same field server.
Allow collector-to-field TCP 8081, field-to-central TCP 9090, central-to-field TCP 8081,
and operator-to-central TCP 8090. Synchronize device clocks.

## Start in order

1. Central: `.venv/bin/python run.py prepare`, then `.venv/bin/python run.py run`.
2. Field: `.venv/bin/python run.py prepare`, then `.venv/bin/python run.py run`.
3. In a second field terminal: `.venv/bin/python run.py provision`. Retry after MN registration
   if the central route is not ready yet. This administrator step contacts both CSEs;
   runtime backup requests use only MN and its Mcc route.
4. Collector: `.venv/bin/python run.py prepare`, then `.venv/bin/python run.py run`.
5. Open `http://CENTRAL_ADDRESS:8090/`. Check `/api` for eight initial machines and subsequent
   readings/results. The default five-minute timeline introduces a ninth machine.

Run stays in the foreground and Ctrl+C stops that node's child processes. Use a terminal
multiplexer or service supervisor for unattended operation. A node lock rejects duplicate
runs. Databases and checkpoints persist in runtime/. Prepare refuses to overwrite existing
CSE configuration; inspect it before explicitly removing it to change network settings.
Changing node.env alone does not rewrite an existing acme.ini.

## ML models on field

Training is explicit. Before starting the field node, run inside its directory:

```bash
QF_STATE_DIR=runtime/state QF_ML_MODEL_DIR=runtime/ml_models .venv/bin/python apps/ml_manage.py generate --dataset runtime/normal.json
QF_STATE_DIR=runtime/state QF_ML_MODEL_DIR=runtime/ml_models .venv/bin/python apps/ml_manage.py train --dataset runtime/normal.json
```

The generated models cover machine-01/02; other machines retain threshold monitoring.
Collector and central do not need trained models.

## Verify and recover

Confirm MN is registered under IN, matching telemetry sample IDs exist in MN and the IN
archive, analysis results arrive, and dashboard /api shows current data. Stop/restart each
node to verify persistence. During central outage the field retains data only within CSE
retention limits; backup retries after recovery. During field outage the collector uses its
bounded local outbox. Process liveness alone does not establish successful processing.
Actual validation scope is recorded in the source repository's docs/VALIDATION.md.
