# ⚡ Aegis Watch — AI Powered Machine Health Guardian

Premium industrial dashboard: dark blue + orange glassmorphism theme, gauges,
charts, and 7 full pages, built modularly so your real ML model and real
data can be dropped in later.

## Folder structure
```
aegis_watch/
├── app.py                  <- RUN THIS. Sidebar nav + page router.
├── pages/                  <- one file per page (render() function each)
│   ├── home.py
│   ├── machine_list.py
│   ├── machine_detail.py
│   ├── analytics.py
│   ├── reports.py
│   ├── alert_center.py
│   ├── settings.py
│   └── live_monitoring.py
├── components/
│   └── widgets.py          <- kpi_card, gauge_chart, machine_card
├── utils/
│   ├── data_utils.py       <- ALL machine data lives here (hardcoded/dummy)
│   └── model_utils.py      <- YOUR ML MODEL PLUGS IN HERE
├── styles/
│   └── theme.py             <- dark theme CSS + status badge helper
├── assets/                  <- put a logo image here if you want one
└── requirements.txt
```

## Run it
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Pages
- **Home** — top bar (plant name, time, connected machines, AI status),
  KPI cards, pie chart, live gauge, trend line, bar comparison, heatmap,
  recent alerts table, recommendations, upcoming maintenance, AI confidence.
- **My Machines** — search / filter / sort / add / edit / delete / export,
  10 machine cards, click "View Full Report" to open detail.
- **Machine Detail** — health + failure-probability gauges, current sensor
  values, health timeline, AI prediction, root cause analysis, report
  actions (CSV real; PDF/Email/Print/Camera/Voice are simulated — see note
  below), maintenance/parts/downtime history tables.
- **Analytics** — accuracy/precision/recall/F1, confusion matrix, ROC curve,
  feature importance, SHAP placeholder, sensor trends, correlation heatmap,
  failure distribution, monthly/yearly failure trend.
- **Reports** — daily/weekly/monthly/yearly, machine-wise/department-wise,
  CSV and Excel export (real), PDF export (simulated).
- **Alert Center** — critical/warning/resolved counts, active alert table,
  notification history, email/SMS/voice buttons (simulated).
- **Live Monitoring** — auto-refreshes every 2 seconds (via
  `streamlit-autorefresh`), sensor cards jitter to simulate real-time data,
  colors update automatically with status.
- **Settings** — theme, dark mode, language, thresholds, notification
  toggles, AI model version, DB status.

## What's real vs. simulated
**Real and working right now:**
- All navigation, all charts/gauges/tables
- CSV and Excel report downloads (actually generate files)
- Search/filter/sort on Machine List
- Live Monitoring auto-refresh

**Simulated (show a message, don't actually perform the action)** — because
they need external services this sandboxed build can't reach:
- Email Report / Email Alert (needs SMTP/SendGrid etc.)
- SMS Alert (needs Twilio or similar)
- Voice Alarm / Voice Assistant (needs a speech/voice AI service)
- Live Camera (needs an RTSP/IP camera feed)
- PDF Report generation (needs a PDF library wired to real data — doable,
  just not included by default; ask if you want this added)
- Add/Edit/Delete Machine (needs a real database to persist to)

## Connect your real ML model
Same as before — only `utils/model_utils.py` needs editing:
1. `joblib.dump(model, "machine_health_model.pkl")` in your notebook
2. Put `machine_health_model.pkl` in the project root (next to `app.py`)
3. `predict_health()` is already wired for a model with features
   `[temperature, vibration, pressure, rpm]` outputting a category label
   ("Healthy"/"Warning"/"Critical"). Adjust if yours differs.

## Connect real data
Edit `utils/data_utils.py` — `MACHINES`, `PREDEFINED_HISTORY`,
`MAINTENANCE_HISTORY`, etc. Replace with real DB/CSV/API calls; keep the
same function names and return shapes and nothing else breaks.

## Tested
Every page was run through Streamlit's `AppTest` framework (executes the
actual script and catches runtime exceptions) with no errors, across all
10 machines including Healthy/Warning/Critical statuses.
