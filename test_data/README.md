# Test Data

Default execution uses test_data_timeline.json. Each 300-second (5-minute) cycle starts with eight machines and adds machine 9 at 120 seconds. For collector-01, machines 1–4 belong to Zone A and 5–8 to Zone B. Assignments are managed in apps/dashboard_sections.json.

- test_data_timeline.json: nine machines, 19 frames, temperature/vibration/current sensors, and one machine's anomaly/recovery per minute.
- test_data_dynamic_timeline.json: the original four-machine delayed-appearance/sensor-addition scenario with five frames; also used by regression tests.
- test_data.json: original two-machine sequential replay with 10 rows; default file for --mode replay.
- test_data_expanded.json: original four-machine sensor-expansion replay with five rows.

Run from the repository root: python apps/collector_ae.py
Explicit replay: python apps/collector_ae.py --mode replay --dataset test_data/test_data_expanded.json
Restart the collector after editing JSON. Replace old apps/test_data*.json paths in commands with their new test_data/ paths.


## Five-Minute Demonstration Schedule

| Elapsed Time | Event |
|---|---|
| 0:00 | Machines 1–4 in Zone A and 5–8 in Zone B start normally |
| 0:30–0:45 | Machine 3 anomaly followed by recovery |
| 1:30–1:45 | Machine 6 anomaly followed by recovery |
| 2:00 | Machine 9 appears, registers automatically, and is displayed under Unassigned |
| 2:30–2:45 | Machine 9 anomaly followed by recovery |
| 3:30–3:45 | Machine 4 anomaly followed by recovery |
| 4:30–4:45 | Machine 8 anomaly followed by recovery |
| 5:00 | Default execution repeats the next cycle |

At most one machine produces anomalous values at a time. During anomaly intervals, temperature is 82°C,
vibration is 8.5 mm/s, and current is 6.5 A. Values return to normal after 15 seconds.
Machine 9 is absent from zone assignments and registers with oneM2M when the collector processes its first reading.
Registered resources and last dashboard data persist across cycles.
To measure exactly one cycle, use:

```bash
python apps/collector_ae.py --mode adaptive --dataset test_data/test_data_timeline.json --cycles 1 --replay-id demo5min01
```

Changing the data file does not delete machines or history already stored in the CSE.
Dashboard anomaly/recovery timing includes analysis and central-copy processing delays.
