# QuietFix Role-Based Access Control

ACP mode is optional. The default `QF_ACP_ENABLED=0` retains the existing development commands and administrator Originator. ACP changes CSE resource permissions, so test injectors must use the collector identity or administrator after activation.

## Permissions

| Resource | Create | Retrieve and Discover | Additional Permissions |
|---|---|---|---|
| MN collector and machine containers | Collector: CNT and CIN | Collector, analyzer, backup management AE | Analyzer and backup management AE may create SUB only |
| MN analysis results | Analyzer: CIN | Analyzer, backup management AE | Backup management AE may create SUB only |
| IN archive | Backup management AE: CNT, CIN, GRP | Backup management AE, dashboard | Separate ACP and macp apply to groups |
| IN telemetryGroup | Backup management AE creates it under archive | Backup management AE, dashboard | Only backup management AE may update the group |
| qf-analyzer subscriptions | Analyzer | Analyzer | Only analyzer may update subscriptions |
| qf-forwarder subscriptions | Backup management AE | Backup management AE | Only backup management AE may update subscriptions |
| ACP itself | Administrator | Roles requiring policy references | Only administrator may update or delete |

Every ACP includes administrator maintenance permissions. CREATE permissions restrict child resource types through `acod/chty`. Permission to create subscriptions does not allow the analyzer to create sensor CINs. Policies are explicitly attached to new machine containers, subscriptions, and groups. Existing CINs remain unchanged and inherit access control from their parent containers.

## Application Procedure

1. Back up the current ACME configuration and resource data. Pause workers and first apply the changes to a separate test instance. CSE access-control enforcement must be enabled.
2. Load the existing `session.env` and check the administrator Originator. The following command changes QuietFix permissions on the CSEs.

```bash
source session.env
export QF_ADMIN_ORIGIN=CAdmin
python apps/access_control.py --apply
```

The program prepares AEs and compares their actual `aei` values with the role Originators. If they differ, set the corresponding `QF_*_ORIGIN` to the reported AE-ID and rerun. The backup management AE registers on MN. IN ACP permits the forwarded `/id-quietfix-mn/Cqfforwarder` identity. Existing IN forwarder resources remain for compatibility but are not accessed directly at runtime. Policies target one `QF_COLLECTOR_ID`; apply them sequentially with each collector ID and Originator for multiple collectors. Keep analyzer, backup management AE, and dashboard Originators unchanged across collectors.

3. Verify allowed and denied operations on the actual CSE.

```bash
python apps/verify_access.py --run
```

The check creates test CINs in temporary containers and verifies role-specific reads and prohibited creation, deletion, ACP changes, and acpi changes. It then removes the temporary containers as administrator. Failures other than HTTP 403 do not count as successful permission checks. Forced termination may leave `qf-acp-check-` temporary containers.

4. Apply the following setting in every application terminal and restart with the existing commands.

```bash
export QF_ACP_ENABLED=1
```

Check subscription notifications, subscription URL changes, group latest-value queries, and automatic registration of new machines. Administrators must provision new gateway AEs first; new machines beneath registered collectors retain automatic resource creation. Existing test JSON files can still be edited or replaced in the same way.

## Existing Data and Development Environments

- Existing resource `acpi` values are replaced with one restrictive policy. Group `macp` is also set. Do not retain other permissive ACPs alongside it.
- Data content and local state files are not deleted. Follow the existing replay-id rules when changing datasets.
- The default administrator development mode still works through maintenance permissions after application. `QF_ACP_ENABLED=0` changes only the request identity selected by applications; it does not remove CSE ACPs.
- To fully restore previous ACPs, restore backed-up per-resource acpi and macp values as administrator. Permission migration uses multiple requests and is not transactional. On failure, keep workers stopped while correcting and rerunning the operation or restoring the backup.
- Unknown existing subscriptions and discovery-limit exhaustion stop the operation rather than being silently ignored. Review the logs. Resources outside the scope and CSEBase policies are unchanged.

## Security Scope

This feature separates permissions by role. An Originator header alone does not authenticate an identity. Production deployment requires authenticated identity-to-Originator binding and TLS. Keep administrator credentials out of runtime environments. This does not automatically harden CSEBase policies for new AE registration, access by other applications, or sender authentication on notification receivers.

Allow/deny logs and policy JSON demonstrate source-reading creation permissions and the dashboard's read-only access.

Automated tests check policy construction, request identities, and regressions using the existing HTTP test double. They do not replace actual ACME permission enforcement. Verify deployment enforcement separately with the live check above.
