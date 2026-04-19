# ECHO: Enhanced Cognitive Human Operations
```
╭───────────────────────────────────────────────────────────╮
│                                                           │
│  ███████╗  ██████╗ ██╗  ██╗  ██████╗                      │
│  ██╔════╝ ██╔════╝ ██║  ██║ ██╔═══██╗   Enhanced          │
│  █████╗   ██║      ███████║ ██║   ██║   Cognitive         │
│  ██╔══╝   ██║      ██╔══██║ ██║   ██║   Human             │
│  ███████╗ ╚██████╗ ██║  ██║ ╚██████╔╝   Operations        │
│  ╚══════╝  ╚═════╝ ╚═╝  ╚═╝  ╚═════╝                      │
│                                                           │
│              USAARL || FAU                                │
│                                                           │
╰───────────────────────────────────────────────────────────╯
```
**Version:** 0.1.2 - Dashboard Enchancments

**Date:** 04/19/2026

**Facilitator:** US Army Aeromedical Research Lab (USAARL) || Operator State Monitoring Team (OSM)

**Developer:** Florida Atlantic University (FAU) || Hacking for Defense Program (H4D)

---

## Table of Contents

- [About](#about)
- [What's New in v0.1.2](#whats-new-in-v012)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Dashboard](#dashboard)
- [Sensors](#sensors)
- [Documentation](#documentation)
- [Tech Stack](#tech-stack)
- [References](#references)

---

## About

ECHO is a real-time platform for monitoring the cognitive state of operators. It connects to physiological sensors (EEG, ECG, eye tracking, etc.) via [Lab Streaming Layer (LSL)](https://labstreaminglayer.org), displays live data on a freeform canvas dashboard, and records everything for offline analysis. Future implementations include a machine learning training and development abstraction environment for quick, easy, and intuitive development of models for research testing.

The end goal of this platform is to provide the means to develop the groundwork for systems that aim to enhance operator state management, monitoring, prediction, and support.

---

## What's New in v0.1.2

This release replaces the grid-based layout with a fully freeform canvas and adds connection-aware alerting.

**Dashboard — Freeform Canvas**
- Monitor panels are now positioned on a free-form ReactFlow canvas — drag anywhere, no grid snapping
- Resize any monitor from the bottom-right grip handle in its footer
- Collapsible stream panel — click the `‹` / `›` chevron to hide/show the sidebar
- Stats monitor time-window selector with `ms`, `s`, `min`, and `samples` units that apply live
- Per-channel selector in the Waveform monitor — isolate a single channel or view all overlaid
- Monitor footer with a color-coded stream latency dot (green < 100 ms · yellow < 300 ms · red ≥ 300 ms)

**Alerts & Error Handling**
- Global alert overlay visible on every tab (top-right toast stack)
- Sensor connection dropout detection with auto-reconnect notification
- Session dropout detection (unexpected stops trigger an error alert)
- Recording dropout detection (stops due to disconnection trigger a warning alert)
- User-initiated stops are distinguished from unexpected drops — no false alerts
- Alerts auto-dismiss after 8 seconds; duplicate alerts are suppressed

---

## What's New in v0.1.1

**Frontend — Monitoring Dashboard**
- Live oscilloscope-style signal rendering via HTML5 Canvas with per-channel display
- Multi-channel support with individual channel isolation or all-channels overlay view
- Per-channel color coding with a built-in color picker
- Automatic stream discovery and live refresh without restarting
- Auto-reconnecting WebSocket with online/offline status indicator
- Navigation scaffolding for Settings, Machine Learning, and Data views

**Backend**
- `start_all_dummy.py` — single-command launcher for all dummy sensors
- Alpha Band Power derived sensor using Welch's method
- Sensor templates directory for dummy, derived, and physical sensors

---

## Project Structure

```
echo/
├── backend/
│   ├── app.py                   
│   ├── requirements.txt
│   ├── dashboard/
│   │   └── session_manager.py         # LSL discovery, WebSocket broadcast, recording
│   ├── sensors/
│   │   ├── sensor.py                  # base class hierarchy (Physical, Derived, Dummy, ML)
│   │   ├── start_all_dummy.py         # launch all dummy sensors in one command
│   │   ├── dummy/
│   │   ├── derived/
│   │   └── templates/
│   └── utils/
│
├── src/                               # React + Tailwind frontend (Vite + Electron)
│   ├── main.jsx
│   ├── App.jsx                        
│   ├── App.css
│   └── assets/
│       ├── components/
│       ├── context/
│       └── views/
│           ├── dashboard/
│           │   ├── monitor/
│           │   └── websocket/
│           ├── data/
│           ├── ml/
│           └── settings/
│
├── docs/
│   └── sensors/
│       ├── ADDING SIMPLE SENSORS.md
│       └── ADDING PHYSICAL SENSORS.md
├── main.js                            # Electron main process
├── preload.cjs                        # Electron preload
├── vite.config.js
├── package.json
└── README.md
```

---

## Quick Start

### 1. Start the Backend

```bash
# install backend dependencies
pip install -r backend/requirements.txt

# terminal 1 — start all dummy sensors at once
cd backend/sensors
python start_all_dummy.py

# terminal 2 — start the session manager (FastAPI)
cd backend
uvicorn app:app --reload --port 8000
```

### 2. Start the Frontend

```bash
# install frontend dependencies
npm install

# terminal 3 — start in browser (Vite only)
npm run dev

# OR start as Electron desktop app
npm run electron:dev
```

Open the URL printed by Vite (typically `http://localhost:5173`). The dashboard will auto-connect to the session manager's WebSocket at `ws://localhost:8000/ws`.

### 3. Monitor Signals

1. Click **Start Session** in the dashboard header
2. In the left panel, find your streams — click **WAVE** or **STATS** to add a monitor
3. Drag monitors freely on the canvas; resize from the bottom-right grip
4. Use the channel dropdown in a Waveform monitor to isolate channels
5. Use the Stats monitor time-window selector to set the rolling window
6. Click **Refresh** to re-scan the network if you start new sensors mid-session
7. Collapse the stream panel with the `‹` button to maximise canvas space

### Terminal-Only Testing

```bash
# watch raw WebSocket data in the terminal
cd backend/utils
python test_monitor.py
```

### Using Real Hardware

For devices with built-in LSL support, open your sensor's LSL app and start streaming before launching the session manager. ECHO discovers any LSL stream on the network automatically. Click **Refresh** in the dashboard to pick up new streams without restarting.

---

## Dashboard

The monitoring dashboard is a freeform canvas for viewing live sensor streams.

**Freeform Canvas** — Powered by ReactFlow. Monitors can be placed anywhere on an infinite canvas. Pan with middle-click or right-click drag. Zoom with scroll wheel.

**Waveform Monitor** — Oscilloscope-style canvas renderer. Supports all-channel overlay or single-channel isolation. Per-channel color coding with a color picker in the header.

**Stats Monitor** — Rolling statistics table (mean, std, min, max) over a configurable time window. Set the window in `ms`, `s`, `min`, or `samples` — updates live.

**Monitor Footer** — Each monitor shows a latency status dot (green/yellow/red) indicating how recently data was received from that stream, plus a resize grip in the bottom-right corner.

**Collapsible Panel** — The left stream/monitor panel can be collapsed to a narrow strip to give the canvas more room.

**Alert Overlay** — A toast stack in the top-right corner shows connection, session, and recording alerts across all tabs. Alerts auto-dismiss after 8 seconds.

---

## Sensors

ECHO uses a class hierarchy to treat all data sources uniformly as LSL streams:

| Type | Purpose | Example |
|------|---------|---------|
| **DummySensor** | Fake data for testing | `FakeECG`, `FakeEEG`, `HiLowSensor`, `TimerSignal` |
| **PhysicalSensor** | Wraps non-LSL hardware (serial, BLE, TCP) | Custom device adapters |
| **DerivedSensor** | Computes metrics from other streams | `AlphaBandPower` |
| **MLSensor** | Applies pre-trained models to buffers | *(planned)* |

### Launching Dummy Sensors

```bash
# all at once (recommended for testing)
cd backend/sensors
python start_all_dummy.py

# or individually
python -m sensors.dummy.fake_ECG
python -m sensors.dummy.fake_eeg
python -m sensors.dummy.hi_low_signal
python -m sensors.dummy.timer_signal
```

To make your dummy sensor auto-launchable by `start_all_dummy.py`, add a `default()` classmethod that returns a pre-configured instance.

See the guides in `docs/sensors/` for how to add your own.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Adding Simple Sensors](docs/sensors/ADDING%20SIMPLE%20SENSORS.md) | Guide for dummy and derived sensors |
| [Adding Physical Sensors](docs/sensors/ADDING%20PHYSICAL%20SENSORS.md) | Guide for wrapping real hardware |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Streaming | Lab Streaming Layer (`pylsl`) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Signal Processing | NumPy, SciPy |
| Frontend | React 19, Tailwind CSS 4, Vite |
| Desktop Shell | Electron |
| Canvas / Node Graph | ReactFlow |
| Visualization | HTML5 Canvas (custom oscilloscope renderer) |

---

## References

ECHO's streaming backbone is built on Lab Streaming Layer. Thank you to the LSL team for an amazing tool.

> Kothe, C., Shirazi, S. Y., Stenner, T., Medine, D., Boulay, C., Grivich, M. I., Artoni, F., Mullen, T., Delorme, A., & Makeig, S. (2025). The Lab Streaming Layer for Synchronized Multimodal Recording. *Imaging Neuroscience*, 3, IMAG.a.136. https://doi.org/10.1162/IMAG.a.136

<details>
<summary>BibTeX</summary>

```bibtex
@article{kothe2025lab,
  title     = {The Lab Streaming Layer for Synchronized Multimodal Recording},
  author    = {Kothe, Christian and Shirazi, Seyed Yahya and Stenner, Tristan
               and Medine, David and Boulay, Chadwick and Grivich, Matthew I.
               and Artoni, Fiorenzo and Mullen, Tim and Delorme, Arnaud
               and Makeig, Scott},
  journal   = {Imaging Neuroscience},
  volume    = {3},
  pages     = {IMAG.a.136},
  year      = {2025},
  publisher = {MIT Press},
  doi       = {10.1162/IMAG.a.136},
  url       = {https://doi.org/10.1162/IMAG.a.136},
  note      = {Open Access}
}
```

</details>