# FlexContainer Sensor Model and Discovery

## Data Model

Each sensor's value, unit, type, and sample identifier are exposed through a typed `qf:sensorReading` FlexContainer. Discovery uses `ty=28`, `cnd=org.quietfix.sensorReading.v1`, and labels to build machine and sensor lists. The analyzer and dashboard use only complete sensor sets whose sample ID, timestamp, machine, and collector match. CINs retain history, support retries, and preserve consistency during partial updates.

## Implementation

- `models/quietfix.fcp`: version 1 model installed in ACME. `value` is a float; `unit` and `sensorType` are explicit strings. Temperature °C, vibration mm/s, and current A are represented directly. This is a QuietFix-specific model, not a standard SDT model.
- `apps/flex_model.py`: model creation/update, actual FCNT discovery, validation, and same-sample joining. Older samples cannot overwrite newer FCNT values.
- The collector and forwarding component write models on MN/IN. If model support is enabled but unavailable on the server, an error is reported. Unsupported requests are not treated as successes.
- The analyzer and dashboard use discovered models. Historical CINs and partially matching sensor updates fall back to CIN processing to avoid mixing timestamps. Samples record the `data_model` used.
- Dedicated ACPs protect FCNTs. Only the collector/forwarding component can update FCNT values on its side; the analyzer/dashboard retrieve them. Existing CNT UPDATE permissions are not expanded.

## Setup

1. Install `models/quietfix.fcp` in **each runtime environment** for MN-CSE and IN-CSE. ACME 2025.11 loads it as an additional model from `init/quietfix.fcp` beneath the runtime base directory after restart. Do not replace default init files or configuration. In containers, deploy this file through a persistent volume or image. Check the additional-model path for the installed version.
2. Load the existing `session.env` and rerun `python apps/access_control.py --apply` to create FCNT policies. Initial policy attachment to an AE without ACP uses the AE owner's identity; later changes use the ACP administrator PVS. Authenticated deployments also require initial provisioning permissions for the AE owner.
3. Set the following in worker and dashboard environments and restart with the existing commands.

```bash
export QF_FLEX_ENABLED=1
export QF_ACP_ENABLED=1
```

Existing JSON and threshold rules are unchanged. FCNTs for historical machines are created when the collector or central-history forwarding runs again. Completed checkpoints prevent retransmission; reprocess with a separate state directory to migrate all historical data. The feature defaults to OFF. Restart applications with `QF_FLEX_ENABLED=0` to disable it. Created FCNTs remain and existing CINs are not deleted.

## Validation

```bash
python -m unittest discover -s tests -v
# After installing acmecse==2025.11 and project dependencies in a separate development environment
QF_RUN_LIVE_ACME=1 python -m unittest discover -s tests -p test_live_acme.py -v
```

Live tests start and stop two standalone ACME instances with in-memory databases on local ports in temporary directories. On ACME 2025.11, four-machine sensor model creation/update, cnd discovery, analysis, central replication, actual group fan-out, and dashboard retrieval passed. FCNT UPDATE by the analyzer and dashboard was rejected with HTTP 403. Sensors with unsupported units remain unassessed.

Unit tests cover model schema, prevention of timestamp regression, incomplete/cross-sample joins, explicit ACPs, query parameters, and existing data compatibility. Verify execution separately after installing the model in the deployed ACME version.

## References

- ACME FlexContainer examples and model format: https://github.com/ankraft/ACME-oneM2M-CSE/blob/master/tests/testFCNT.py
- Additional model installation: https://acmecse.net/help/FAQ/
