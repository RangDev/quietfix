# SAREF meaning and unit mapping

Plan and implementation: retain the existing FlexContainer projection and add oneM2M semanticDescriptor children (ty 24, RDF/XML dcrp 4). RDF uses the SAREF 3.1.1 Sensor, Measurement, makesMeasurement, relatesToProperty, hasValue, isMeasuredIn and hasTimestamp pattern. Temperature uses the SAREF Temperature class. VibrationRMS and ElectricCurrent are explicitly QuietFix extension classes, not invented SAREF classes. Units use QUDT unit IRIs where known. Unknown properties/units use explicit local extension IRIs and remain unassessed by existing rules.

Enable QF_SEMANTIC_ENABLED=1 together with QF_FLEX_ENABLED=1 on collector, analyzer, forwarder and dashboard. Re-run access_control.py --apply to grant descriptor creation under FCNT; existing container UPDATE privileges are not widened. The CSE must support semanticDescriptor. Existing FCNT descriptors are populated when samples are published/replayed. No physical-device driver discovery is provided.

The CSE discovers SMD resources and returns their RDF. A local rdflib SPARQL query matches property meaning and only accepts resource paths belonging to returned descriptors. This is client-side RDF query, not a claim of server-side ontology inference or native semantic query support. Run `python apps/semantic_query.py --property temperature` or append `--central` to query the archive. Full application discovery uses these descriptors to reconstruct machine catalogs.

Explicit normalization accepts temp/temperature with Celsius, Fahrenheit or kelvin and converts to degrees Celsius; mA current becomes A; m/s vibration becomes mm/s. Conversion occurs before analysis and typed publication. Unknown units are never guessed. Physical sampling, thresholds and legacy mode remain unchanged; semantic mode changes recognized input representations and generated output to canonical units. Source test JSON is not edited. Keep original upstream payloads separately if raw vendor evidence is required.

Validation: test_semantics.py checks different vendor names, Fahrenheit conversion at 75 C threshold, actual RDF SPARQL matching, unknown units and malicious path rejection. QF_RUN_LIVE_ACME=1 QF_RUN_SEMANTIC=1 runs isolated actual ACME semantic storage/discovery, analysis, notification, archive and dashboard validation. Tests do not deploy to the user VM.

References: https://saref.etsi.org/core/v3.1.1/ and http://qudt.org/vocab/unit/ . This implements a SAREF-linked project model, not SDT certification or complete ontology reasoning.
