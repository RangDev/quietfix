# Single-VM deployment

This directory is self-contained. Copy the whole directory to a Linux host with Python 3.12.
No files from the source repository or distributed package are required.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r standalone/requirements-lock.txt
.venv/bin/python standalone/manage.py prepare
.venv/bin/python standalone/service.py start
```

Open http://127.0.0.1:8090 . Stop with `.venv/bin/python standalone/service.py stop`.
See [the deployment guide](docs/DEPLOYMENT.md) for ML training and operation.
Skip the repository clone step when using this package. Models must be trained explicitly.
Optional repository tests are not included in this deployment package; the self-contained
`standalone/smoke_test.py` checks actual ACME integration after stopping running services.
