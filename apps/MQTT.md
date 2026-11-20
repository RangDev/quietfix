# Collector oneM2M MQTT Binding

## Communication Architecture

The collector–MN-CSE link supports the oneM2M TS-0010 JSON request/response binding. It does not publish sensor JSON to arbitrary MQTT topics for an HTTP bridge. ACME directly processes MQTT request primitives. The analyzer, forwarding component, and dashboard retain HTTP.

A persistent connection and QoS 1 are used, but publish success or PUBACK alone does not establish successful storage. The client waits for the final CSE oneM2M response with a matching `rqi`. Existing collector retries and the persistent outbox handle disconnections and timeouts; there is no automatic HTTP fallback.

## Implementation

- `mqtt_client.py`: connection, SUBACK validation, request primitive construction, response-topic/rqi checking, oneM2M RSC error conversion, timeouts, reconnection, and resubscription. Uses `paho-mqtt==2.1.0`.
- `onem2m_client.collector_client()`: explicit protocol selection. Reuses the MQTT connection across adaptive-collector calls and closes it on exit.
- Both bindings share existing `ensure`, `put`, and CIN conflict-checking logic. Retransmissions of the same sample_id use the same CIN name.
- MQTT mode requires AE provisioning and ACP mode. Requests cannot switch to administrator or another Originator over an established MQTT connection.
- Response topics are `/oneM2M/resp/<AE-ID>/<CSE-ID>/json`; request topics are `/oneM2M/req/<AE-ID>/<CSE-ID>/json`. Leading `/` is removed from IDs and internal `/` becomes `:`. Any configured topicPrefix is prepended.

## Server and Broker Preparation

1. Deploy an MQTT broker reachable from both the collector and MN-CSE. ACME itself is not a broker.
2. Enable the MN-CSE MQTT binding and connect it to the same broker. The following is a verified ACME 2025.11 configuration example. Replace the host/port and restart.

```ini
[mqtt]
enable=true
address=127.0.0.1
port=1883
```

Inside a container, 127.0.0.1 refers to that container. Use a reachable service name or IP for an external broker. Check MQTT support and setting names for the installed ACME version.

3. Run `python apps/access_control.py --apply` through the existing administrator HTTP path to prepare AEs and ACPs. If using FlexContainer, install the model on both CSEs first.
4. Install dependencies with `pip install -r apps/requirements.txt`.

## Collector Execution

Load the existing session.env, then set the following in the **collector terminal**.

```bash
export QF_ACP_ENABLED=1
export QF_COLLECTOR_PROTOCOL=mqtt
export QF_MQTT_URL=mqtt://BROKER_HOST:1883
export QF_MQTT_CSE_ID=/ACTUAL_MN_CSE_ID
# Add only if the model is installed
export QF_FLEX_ENABLED=1
python apps/collector_ae.py --dataset test_data/test_data_expanded.json --mode replay --cycles 1 --interval 0.1 --replay-id mqtt-demo
```

`QF_MQTT_CSE_ID` is the actual CSEBase `csi`, not the MN_BASE resource name or IP address. Administrator provisioning uses HTTP; runtime collector requests use MQTT. Other applications retain their existing commands. Data files, rules, and sample_id formats are unchanged. Reusing a completed replay-id may skip transmission because of existing checkpoints.

To return to HTTP, set `QF_COLLECTOR_PROTOCOL=http` and restart the collector. HTTP is the default. Changing broker settings alone does not change a running process's environment variables.

## Authentication and TLS

Apply user authentication, topic ACLs, and TLS to remote production brokers. `mqtts://HOST:8883` validates certificates; specify QF_MQTT_CA_FILE if needed. Supply credentials through QF_MQTT_USERNAME and QF_MQTT_PASSWORD rather than the URL. Do not commit actual credentials.

Broker ACLs must restrict collectors to writing their own request topics and reading their own response topics. The CSE needs permissions for its request, response, and registration topics. Configure CSE authentication separately. Originator strings and ACP alone do not authenticate senders. Local integration tests used an anonymous loopback broker. Authenticated/TLS broker operation requires separate validation.

## Validation

Standard tests:

```bash
python -m unittest discover -s tests -v
```

With ACME 2025.11, amqtt 0.11.3, and project dependencies installed in a separate development environment, this test starts an actual broker and two ACME instances on temporary ports with in-memory databases.

```bash
QF_RUN_LIVE_ACME=1 QF_RUN_MQTT=1 python -m unittest discover -s tests -p test_live_acme.py -v
```

Checks:

- Actual oneM2M MQTT CREATE/RETRIEVE/UPDATE and discovery-parameter mapping
- Four-machine FlexContainer/CIN storage followed by HTTP analysis, forwarding, group retrieval, and dashboard display
- No duplicate CINs on retransmission
- Actual HTTP subscription notifications for CINs created through MQTT
- Collector attempts to create analysis results map to an HTTP-compatible 403 error
- Timeout on broker shutdown; automatic reconnection, resubscription, and request recovery after restart
- Ignoring invalid response topics/rqi/identities, rejecting PUBACK-only success, and HTTP-mode compatibility

Validate the same paths after applying broker and ACME MQTT settings in the deployment environment. Traffic, power, and latency improvements have not been measured.

## References

- oneM2M MQTT primitive mapping: https://specifications.onem2m.org/ts/ts-0010/latest/6.5/
- ACME MQTT binding: https://github.com/ankraft/ACME-oneM2M-CSE/blob/master/acmecse/plugins/bindings/MQTTClient.py
