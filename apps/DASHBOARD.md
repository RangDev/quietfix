# Machine Cards by Zone and Detail Panel

The dashboard retrieves machine data and analysis results from IN-CSE.

Cards show only the machine name, identifier, and analysis status. Normal is green, detected anomalies are red, and unassessed, awaiting-data, and pending-analysis states are gray. Selecting a card opens sensor values, units, per-sensor results, analysis method, measurement/delivery times, and sample_id in the right panel. On mobile, the panel appears above the cards. Close it with the close button or Escape; select cards with Enter/Space. Selection and keyboard focus persist across automatic refreshes.

By default, `dashboard_sections.json` assigns collector-01 machines machine-01 through machine-04 to Zone A and machine-05 through machine-08 to Zone B. Identical machine IDs under different collectors identify different machines. New unassigned machines appear automatically under Unassigned. Empty zones are hidden. Edit names and assignments using this format:

```json
{"sections":[{"id":"line-a","name":"Production Line A","machines":[{"collector_id":"collector-01","machine_id":"machine-01"}]}]}
```

To use another file, set `QF_DASHBOARD_SECTIONS=/absolute/path/sections.json` for the dashboard process. Configuration is reread on queries, so assignments can change during execution. Duplicate machine assignments and zone IDs are errors. If a query fails, the last valid data is retained with an error indication. The `unassigned` ID is reserved.

A green card means the last valid analysis was normal; it does not guarantee machine power or application health. Query failures turn existing green/red cards gray and retain the previous result as secondary text. Unassessed sensors are distinguished in the detail panel. Per-sample age-based health classification and a separate health monitor are not supported.

Execution: update the entire apps directory and restart with `python apps/dashboard.py`. Deploy dashboard.html and dashboard_sections.json with the Python code. No sensor JSON changes are needed beyond the default assignment configuration.

Validation: standard unittest tests check configuration and collection/analysis/query regressions. Optional `QF_RUN_UI=1 python -m unittest discover -s tests -p test_dashboard_ui.py -v` requires Playwright Chromium and checks hidden card values, zones/Unassigned, detail selection and updates, focus/keyboard behavior, connection errors, and mobile horizontal overflow. Set QF_CHROMIUM=/path/to/chromium to use a system browser. UI tests use a mocked API.


## Analysis Result Updates

While awaiting new analysis, each machine retains the last result for the same collector and machine.
If no initial result exists, analysis is pending and is not treated as normal. New results update
the normal, anomalous, or unassessed status. When analysis predates the latest measurement,
the card shows “Analyzing latest data · Last known result”.

“Analysis delayed” appears after the default 60 seconds from the analyzed measurement time.
If no initial result exists, the dashboard also tracks when it began waiting.
Even if new readings keep arriving, no initial result for 60 seconds triggers the delayed indication.
Configure this through `QF_ANALYSIS_STALE_SECONDS`.
The last result remains during delays but does not establish the current status.
The detail panel separates the latest measurement time/sample from the analyzed time/sample.
When samples differ, latest sensor values show analysis pending rather than receiving previous per-sensor results.
Query errors retain the gray query-error state and previous result.
