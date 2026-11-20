# Standalone oneM2M Execution

For initial setup, follow the [integrated deployment guide](../docs/DEPLOYMENT.md), including ML training and service start/stop/status/logs. This guide covers manual operation of individual CSEs and AEs.

ACME IN/MN run as host Python processes without MEC Sandbox, Kubernetes, OAuth, or ingress. The baseline is Linux, Python 3.12, and pinned ACME 2025.11. Each CSE persists its database as a TinyDB file. The loopback HTTP/CAdmin configuration is for development and is not secured for public exposure.

## Preparation

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r standalone/requirements.txt
.venv/bin/python standalone/manage.py prepare
```

Existing VM MEC installations and databases are unchanged. Check for conflicts on ports 8081/8082/9090/8090/8091/8092 first. Do not run old and new applications with the same ports/collector IDs simultaneously. prepare preserves existing acme.ini and session.env files. Model files are copied from the repository version. Check resourcesPath in acme.ini after moving runtime directories or reinstalling the virtual environment.

## Execution

Run each command in a separate terminal. Start IN before MN.

```bash
.venv/bin/python standalone/manage.py in
.venv/bin/python standalone/manage.py mn
.venv/bin/python standalone/manage.py check
```

check verifies actual CSE types and retrieves MN through Mcc from IN. If it fails immediately after registration, inspect MN/IN logs and rerun after registration completes. Load the environment from the repository root in every application terminal.

```bash
source runtime/standalone/session.env
```

On initial setup and upgrades, stop workers and run the following as administrator first.

```bash
.venv/bin/python apps/setup_resources.py
```

This permits the SP-relative identity forwarded by MN in the IN archive permissions. Data is physically stored in the IN-CSE database. Add `QF_IN_CSE_ID=/id-quietfix-in` and `QF_MN_CSE_ID=/id-quietfix-mn` to existing session.env files. CSEBase names and CSE-IDs are different values.

Then run each command below in a separate terminal.

```bash
.venv/bin/python apps/analyzer_ae.py
.venv/bin/python apps/backup_ae.py
.venv/bin/python apps/dashboard.py
.venv/bin/python apps/collector_ae.py
```

The dashboard is at http://127.0.0.1:8090. Use an SSH tunnel for a VM accessed from Windows. The default eight machines remain split four each across Zones A/B. The backup management AE connects over Mca only to MN-CSE. MN-CSE forwards central-copy requests over Mcc to IN-CSE.

Shutdown: press Ctrl+C in each terminal in collector → analyzer/backup management AE/dashboard → MN → IN order. Restart in reverse order. Do not delete CSE databases or application state under runtime/standalone. Back up the entire folder after cleanly stopping applications and CSEs. Automatic migration from the old MEC in-memory database is not provided.

## Optional Features

- ACP: load the environment, run apps/access_control.py --apply, then set QF_ACP_ENABLED=1 for every application. See apps/ACP.md.
- FCNT/semantic information: prepare copies models into each CSE's init directory. Confirm loading, then follow option/permission setup in apps/FLEX.md and SEMANTICS.md.
- MQTT/mTLS remain independent features. MQTT requires a separate broker and ACME binding configuration. manage.py defaults to --no-mqtt; remove this flag for MQTT tests and configure authentication, CA, and broker settings. The HTTP gateway supports a loopback backend. Removing MEC does not resolve CSE MQTT/outbound-notification certificate limitations. See apps/MQTT.md and security/README.md.
- Planned transfer: run another MN with manage.py backup and prepare shared QF_ROUTE_FILE/ACP according to apps/HANDOVER.md. Transfer from A to B while A is alive; this is not automatic failover.

Check actual notifications, permissions, and eight-machine data paths using application logs and sample_id. Run unit tests and actual CSE integration tests separately.

## Reproducible Validation

Stop existing CSEs and run `.venv/bin/python standalone/smoke_test.py`. The test refuses to run if 8081/9090 are occupied. It creates fresh IN/MN instances and databases in a temporary directory, checks actual CSE types, Mcc remote retrieval, and eight-machine storage/analysis/central copies/dashboard API, then shuts them down. This uses a development administrator identity for Mcc and is separate from role-based security validation. Run standard regressions with `.venv/bin/python -m unittest discover -s tests -v`. This does not establish sustained throughput, persistence across reboot, all TLS features, or UI interaction validation.


## Backup Management AE and Mcc

Run analysis and backup management AEs as separate processes on the field MN device. Analysis classifies measurements and stores local results. Backup management reads raw measurements, equipment/sensor lists, and analysis results, creates independent central copies, and handles retries.

Path: backup management AE → Mca → MN-CSE → Mcc → IN-CSE. The IN archive is an AE resource for storage, not a separate program. The backup AE has no direct Mca connection to IN. The dashboard connects over Mca to IN on the central device. Administrator provisioning directly accesses both CSEs, separately from the runtime backup path.

The executable is `apps/backup_ae.py`. `forwarder_ae.py` is a compatibility entry point for the same Mcc implementation. Internal AE name `forwarder`, identity `Cqfforwarder`, `QF_FORWARDER_*`, and `state/forwarder.sqlite3` remain for resource/ACP/subscription/state continuity. Do not run both entry points together. Notifications, periodic reconciliation, checkpoints after success, and deterministic CIN names preserve retries. Only data retained on MN can be copied after an outage, so recover before retention limits are exceeded.

In ACP mode, `access_control.py --apply` prepares the local read identity and IN permissions for `/id-quietfix-mn/Cqfforwarder`. Set `QF_MN_CSE_ID` for custom MN IDs. Before transferring MN, permit the target MN's SP-relative backup identity in IN ACP too. With TLS, the backup AE's HTTP peer is MN; bind its identity certificate to the MN gateway.
