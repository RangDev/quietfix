# Independent deployment packages

Run `python tools/build_packages.py` from a source checkout. The default output is dist/:

- single-vm/: existing standalone deployment and all runtime source/configuration/data.
- distributed/: collector/, field/, central/, each with local source and a role runner.
- manifest.json: SHA-256 hashes of packaged files.

Python 3.12 and external dependencies must be installed on each target. Packages contain
no virtual environment, database, credentials, local environment files, or trained model.
Build uses an empty destination to avoid deleting deployed runtime state. For another build,
choose a new path with `--output /path/to/new-packages`. Edit common source and templates,
then regenerate; do not edit generated application copies. No branch split is required.

The distributed node guide is [here](../deploy/distributed/README.md). The original
[standalone workflow](DEPLOYMENT.md) remains supported. Dist is generated and excluded
from Git; source code and deployment templates remain tracked. Archive or transfer the
resulting directories for deployment. Real three-device networking must be verified in
the target environment; local process testing does not prove physical deployment.
