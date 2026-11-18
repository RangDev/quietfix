# Controlled MN-CSE transfer

Plan: serialize active CSE operations, snapshot retained telemetry/results and subscriptions, provision the target AEs/ACPs, reconstruct machine metadata and typed/semantic projections, verify each copied sample/result and required subscription, then atomically commit the shared route. Preserve source resources and local worker checkpoints. This is application-managed CSE handover, not native network mobility or automatic failure detection.

Scope: one configured collector gateway with any number of machines; workers on one Linux host share QF_ROUTE_FILE and its flock lock. All collector/analyzer/forwarder processes must run this version with the same route file. External writers, multiple independent hosts or old workers are not covered by the barrier. Other gateways cause an explicit refusal. Source CSE must remain readable; sudden loss before the snapshot is not recoverable by this controller. Only retained source CINs are copied, not already-expired history. Discovery limits fail rather than silently truncating.

Set up a target CSE with the same FlexContainer model and semanticDescriptor support if enabled. Keep IN-CSE unchanged. Configure target HTTPS CA/client identities or MQTT credentials and broker ACLs before transfer. The administrator needs access to both CSEs and the existing IN-CSE; runtime identities remain separate. Target ACPs are rebuilt from QuietFix role policies, not arbitrary external policies. Unknown subscriptions require manual review.

Create a private directory and initialize a route JSON with `url`, `base`, `cse_id`, and optionally `mqtt_url` matching the active source. For example:

```json
{"url":"http://127.0.0.1:8081","base":"mn","cse_id":"/id-mn","mqtt_url":"mqtt://127.0.0.1:1883"}
```

Set `QF_ROUTE_FILE=/private/quietfix/route.json` and `QF_ACP_ENABLED=1` in every worker shell, then restart those workers. Grant them access to the private directory/route/lock; protect it from untrusted users because it controls endpoints. The controller also uses the same file:

```bash
python apps/handover.py --target-url http://127.0.0.1:8082 --target-base backup --target-cse-id /id-backup
# MQTT collectors additionally require --target-mqtt-url mqtt[s]://BROKER:PORT
```

While the exclusive lock is held, guarded publish/analysis/forwarding/subscription operations wait. The adaptive measurement thread can continue filling its existing bounded outbox; overflow policy is unchanged. On success workers refresh the route on their next operation, HTTP clients change endpoints, and MQTT collectors obtain a target connection. MQTT target readiness is checked before committing. Existing source sockets/resources may remain until process exit; there is no source data deletion.

A persistent `.handover.json` journal records preparation, verification, committed/failed status, copied counts, missing retained samples and elapsed controller time. Route replacement is the commit point. Failure before it keeps the source route; partial target resources remain for inspection/idempotent retry. A crash before replacement also leaves the source route. A crash after replacement leaves the new route even if the final journal write did not finish; inspect the route as authoritative. Do not manually revert a route without considering samples generated after the switch.

Elapsed controller time measures the planned barrier, not measured full end-to-end service interruption. Source duplicate samples retain deterministic names; unchanged local analyzer checkpoints work because analysis results are migrated. The forwarder sees new source paths, rechecks retained samples and relies on central idempotent CIN writes to avoid duplication. New samples after switching are analyzed and delivered normally.

Validation: test_routing.py checks the shared/exclusive barrier, atomic JSON replacement and invalid routes. `QF_RUN_LIVE_ACME=1 QF_RUN_HANDOVER=1 python -m unittest discover -s tests -p test_live_acme.py -v` runs three isolated actual CSEs, a failed target retaining the original route, verified migration, subscription notification and post-switch analysis/central delivery. Add QF_RUN_MQTT=1 and QF_RUN_SEMANTIC=1 to exercise the combined modes with an actual local broker. User VM deployment is separate. Automatic conditions, multi-host coordination and permanent source failure recovery are not implemented in this item.
