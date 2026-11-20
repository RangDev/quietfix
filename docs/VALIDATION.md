# Validation Record

Validation date: 2026-11-20. Scope: service management and Python source cleanup.

## Environment

- Debian GNU/Linux 13.7 (Linux), Python 3.12.14
- ACME 2025.11, scikit-learn 1.8.0, joblib 1.5.3
- Complete Python package versions: [requirements-lock.txt](../standalone/requirements-lock.txt)
- Ubuntu 24.04 is the deployment target; validation used Debian.
- Default HTTP/CAdmin loopback configuration. TLS, UI, and optional live-environment tests are distinguished from the skipped regression tests below.

## Results

| Check | Result |
|---|---|
| Python syntax compilation | apps/standalone/tests passed |
| Complete unittest suite | 63 passed out of 66; 3 optional tests skipped |
| Executable syntax comparison for 44 existing Python files | ASTs identical after excluding docstrings; string values preserved |
| Static inspection of all 46 Python files | Zero comment tokens, docstrings, and literal Korean characters |
| Actual ACME smoke test | IN/MN types, Mcc retrieval, eight-machine source/analysis/central copies, and dashboard snapshot passed |
| Backup path | Direct HTTP only to MN; Mcc central-copy consistency, restart deduplication, groups, and role ACP verified |
| Manager execution | Six-service startup, status, and analyzer log retrieval passed |
| ML end-to-end check | API model_state=ready for two machines; measurement/result sample_id matched |
| Shutdown and restart | Passed while preserving databases, trained models, and checkpoints |
| Conflict prevention | Duplicate start and occupied dashboard port rejected |

The manager was tested in the same Linux process environment using start → status → API query →
duplicate-start rejection → logs → stop → status → restart → stop → port-conflict rejection.
ML replay used 5 seconds per row. A CI workflow was added; remote GitHub Actions execution
results are not included in this local validation record.

## Reproduction Commands

```bash
.venv/bin/python -m compileall -q apps standalone tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python standalone/smoke_test.py
```

For actual service execution, ML data generation, evaluation, and API checks, follow the [deployment guide](DEPLOYMENT.md).
Stop existing CSEs on 8081/9090 before the smoke test.
Results with optional tests disabled do not establish complete browser UI or TLS validation.

## Synthetic ML Evaluation Example

Normal training data used seed=42 and 1,000 samples per machine.
Independent testing used seed=123 and count=100, with 50 normal and 50 anomalous samples per machine.

| Machine | TP | FP | TN | FN | Detection Rate | False-Positive Rate |
|---|---:|---:|---:|---:|---:|---:|
| machine-01 | 49 | 0 | 50 | 1 | 98% | 0% |
| machine-02 | 47 | 1 | 49 | 3 | 94% | 2% |

These are raw ML results from a small synthetic test. They do not include consecutive-three alert logic,
network/backup delays, or actual equipment failure prediction. Different sample counts or seeds change the results.

## Limitations

Fast repeated replay at 0.1 seconds per row showed analysis and central copies falling behind latest readings,
leaving the API waiting_for_analysis state persistent. This does not establish sustained throughput.
Verify actual sample_id matching at the guide's default intervals.
Process RUNNING and HTTP responses alone do not establish completed data processing.
Startup after reboot, long-duration load, distributed equipment, and physical sensors were not tested.

In the source-cleanup revision described above, Korean strings used Unicode escapes to preserve existing UI text
and string values. The English translation merged into main translates those runtime strings. Code explanations are provided in Markdown.

## English Branch Validation (2026-11-20)

- Base: main commit `764ddc9` (`Update test data`).
- All 79 tracked files scanned, including Unicode-escaped strings: no remaining Hangul.
- Markdown, dashboard labels, zone names, sensor labels, and synthetic machine names translated to English.
- Dashboard language and date/number formatting changed to English (en-US); browser-local time is retained.
- Python compilation, JSON parsing, and `git diff --check` passed.
- Python AST comparison confirmed that changes in Python files affect only string constants.
- `python -m unittest discover -s tests -v`: 75 tests, 72 passed, 3 optional tests skipped.
- The optional Playwright UI test was attempted with system Chromium. Chromium could not start because socket creation was denied by the execution environment; browser/mobile rendering was not verified.
- Live ACME integration was not rerun for this translation. Earlier results above describe their original validation revisions.
- Existing runtime databases are not migrated; previously stored user-defined names retain their saved values.

## Post-Merge Cleanup (2026-11-20)

- Reviewed merged main commit `e41f879`.
- Scanned all 79 tracked files for literal and Unicode-escaped Hangul; none remained.
- Updated installation instructions, branch descriptions, and CI triggers for main.
- Removed the old forwarder entry point; regression and optional live tests now use backup_ae.py.
- Removed apps/VALIDATION.txt, an earlier feature-validation log superseded by this record.
- Retained optional feature modules, security examples, and datasets referenced by documentation or tests.
- Python compilation, JSON parsing, local Markdown links, and whitespace checks passed.
- Unittest discovery: 75 tests, 72 passed, 3 optional tests skipped (live ACME, broker TLS, browser UI).
- Standalone ACME smoke test passed: IN/MN types, Mcc routing, eight-machine source/analysis/archive/dashboard,
  MN-only backup HTTP, matching central copies, restart deduplication, group membership, and role ACP.
- User VM deployment and optional browser UI/MQTT TLS integrations were not performed for this cleanup.

## Independent Deployment Packages (2026-11-21)

- Base: main commit `3de0034`. Original standalone commands remain unchanged.
- Build creates single-vm/ and distributed/{collector,field,central}/ from shared source.
- Package tests passed: file hashes, relocated node commands/configuration, overwrite refusal,
  and exclusion of runtime state, private keys, and trained models.
- Existing regression suite: 75 tests, 72 passed, 3 optional integrations skipped.
- Two new package tests passed separately.
- Generated packages copied outside the source checkout: actual ACME central/field processes
  and a separate collector runner populated eight machines with telemetry and analysis in the
  central dashboard API. Field provisioning and Mcc archive delivery succeeded.
- The relocated single-VM package passed its actual ACME smoke test.
- Distributed validation used separate process roots on loopback on one Linux host; it does
  not establish physical three-device connectivity, firewall configuration, TLS, or reboot supervision.
- CI now builds packages, runs the generated single-VM smoke test, and uploads dist as an artifact.
  Remote CI execution is not included in these local results.
