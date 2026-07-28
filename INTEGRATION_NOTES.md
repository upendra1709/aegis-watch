# Integration Notes — Live Simulator + Alert Engine

This is your `aegis_final` project with the two new backend modules fully
wired in and adapted to your actual project (not dropped in as generic
standalone files). Summary of what changed:

## New files (root)
- `db_manager.py` — no longer opens a second database. It reuses your
  existing `aegis.db` (via `utils/db_utils.py`) and just adds two new
  tables alongside your existing ones: `machine_status` and `alerts`.
- `sensor_simulator.py` — rewritten to generate the **exact feature
  space your trained model expects** (`air_temp`, `process_temp`, `rpm`,
  `torque`, `tool_wear`), and writes straight into your **existing**
  `readings` table using your **existing** machine IDs (`M-01`..`M-10`).
  Each machine gets a distinct, gradually-evolving fault profile (see
  the module docstring) instead of random noise, and every profile
  picks up from that machine's actual latest reading in the DB so it
  continues smoothly from your seeded demo data.
- `alert_engine.py` — the state machine (state-change detection,
  3-cycle consecutive validation, cooldown, escalation, auto-resolution,
  full history) is unchanged in spirit, but its three "INTEGRATION
  POINT" functions now call your **real trained model**
  (`utils.model_utils.predict_health`) directly — no fallback/mock
  logic left in the code path.

## Files changed
- `app.py` — starts both background threads once per session
  (`start_simulator_thread()` / `start_alert_engine_thread()`), guarded
  by `st.session_state.backend_started` so reruns don't spawn duplicates.
- `pages/live_monitoring.py` — now reads real data from
  `alert_engine.get_all_machine_status()` / `get_latest_reading()`
  instead of adding random jitter to a static baseline reading.
- `pages/alert_center.py` — now reads real, persisted alerts from
  `alert_engine.get_active_alerts()` / `get_alert_history()` instead of
  recomputing "is anything currently abnormal" from scratch every
  rerun. This is what actually fixes the "alerts again and again"
  problem — an active alert is now cooled down, not re-fired, until it
  changes state or resolves.

## Untouched
Home, My Machines, Machine Detail, Analytics, Reports, and Settings
needed **no changes** — they already read from `utils/data_utils.py` /
`utils/db_utils.py`, which reads from the same `readings` table the
simulator now feeds live data into. They'll just start showing real,
continuously-changing values automatically once the app is running.

## Running it
Nothing new to install — no new dependencies. Just run as usual:

```bash
streamlit run app.py
```

The first render of `app.py` starts both background threads. Give it
~10–15 seconds (a few 3-second ticks) for the first live readings and
health scores to appear on Live Monitoring / My Machines / Home.

## Tuning
| Setting | Where | Default |
|---|---|---|
| Reading interval | `sensor_simulator.py` → `TICK_SECONDS` | 3s |
| Alert eval interval | `alert_engine.py` → `CYCLE_SECONDS` | 3s |
| Consecutive cycles before confirming a state change | `alert_engine.py` → `CONSECUTIVE_REQUIRED` | 3 |
| Machine → fault-profile assignment | `sensor_simulator.py` → `PROFILE_SEQUENCE` | see docstring |

## Verified
Ran a 120-tick fast-forward simulation directly against these files
(bypassing Streamlit's UI loop): readings streamed into the existing
`readings` table, the alert engine correctly triggered Warning/Critical
transitions with real model-driven root causes (e.g. "Heat Dissipation
Risk", "Power Failure Risk — motor overloaded", "Overstrain Risk") for
the machines whose profiles were designed to drift into those failure
modes, with no duplicate alerts across repeated cycles in the same
state, confirming cooldown works as intended.
