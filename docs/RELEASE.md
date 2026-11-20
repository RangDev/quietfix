# Release Information

This is a oneM2M-based equipment-monitoring prototype. The current implementation is on `main`; this English version is on `english`.
It includes standalone ACME MN/IN-CSEs, collection, analysis, backup management AEs, and a central dashboard.
Central-copy requests pass from MN-CSE to IN-CSE over Mcc.
Per-machine Isolation Forest models operate alongside threshold monitoring.

## Execution and Validation

- [Deployment procedures](DEPLOYMENT.md)
- [Validation environment and results](VALIDATION.md)
- Service management: `standalone/service.py start / stop / status / logs`
- Trained models: explicitly generated from normal data
- Default configuration: single Linux host with loopback HTTP for development

Models, databases, and environment files are excluded from Git.
Performance validation uses synthetic data; failure-prediction performance on actual equipment has not been validated.
