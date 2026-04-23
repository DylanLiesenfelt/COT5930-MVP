





#ECHO Backend — FastAPI Application

#Main entry point for the backend server.
#Uses SessionManager for all LSL/WebSocket logic.


import logging
import subprocess
import sys
import json

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from dashboard.session_manager import SessionManager
from machine_learning.router import router as ml_router
import os
import pandas as pd

SENSOR_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "sensors", "sensor_config.json")
STORAGE_PATH = './data/CSV'

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
session = SessionManager()

_sensor_proc: subprocess.Popen | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await session.stop()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ml_router)

# ════════════════════════════════════════════════════════════════════
# INFO
# ════════════════════════════════════════════════════════════════════
@app.get("/")
async def root():
    return {
        "app": "ECHO",
        "description": "Enhanced Cognitive Human Operations — a research tool for monitoring, recording, and processing physiological data with machine learning.",
        "repo": "https://github.com/JSerrano98/COT5930-MVP",
        "status": session.status,
    }

@app.get("/health")
async def health():
    return {"status": "ok", "session": session.status}

# ════════════════════════════════════════════════════════════════════
# SESSION
# ════════════════════════════════════════════════════════════════════
@app.post("/session/start")
async def start_session():
    if session.status == "Online":
        return {"ok": True, "status": session.status}
    session.start()
    return {"ok": True, "status": session.status}

@app.post("/session/stop")
async def stop_session():
    await session.stop()
    return {"ok": True, "status": session.status}

# ════════════════════════════════════════════════════════════════════
# STREAMS
# ════════════════════════════════════════════════════════════════════
@app.get("/streams")
def list_streams():
    return session.list_streams()

@app.post("/refresh")
def refresh_streams():
    return session.refresh()

# ════════════════════════════════════════════════════════════════════
# RECORDING
# ════════════════════════════════════════════════════════════════════
@app.post("/record/start")
def start_recording():
    session.start_recording()
    return {"recording": True}


@app.post("/record/stop")
def stop_recording():
    session.stop_recording()
    return {"recording": False}

# ════════════════════════════════════════════════════════════════════
# SENSORS
# ════════════════════════════════════════════════════════════════════

@app.get("/sensors/status")
def sensors_status():
    global _sensor_proc
    running = _sensor_proc is not None and _sensor_proc.poll() is None
    return {"running": running}


@app.post("/sensors/start")
def start_sensors():
    global _sensor_proc
    if _sensor_proc is not None and _sensor_proc.poll() is None:
        return {"ok": True, "status": "already_running"}

    script = os.path.join(os.path.dirname(__file__), "sensors", "start_all_sensors.py")
    _sensor_proc = subprocess.Popen(
        [sys.executable, script],
        cwd=os.path.dirname(__file__),
        env={**os.environ, "PYTHONPATH": os.path.dirname(__file__)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {"ok": True, "status": "started", "pid": _sensor_proc.pid}


@app.post("/sensors/stop")
def stop_sensors():
    global _sensor_proc
    if _sensor_proc is None or _sensor_proc.poll() is not None:
        _sensor_proc = None
        return {"ok": True, "status": "not_running"}
    _sensor_proc.terminate()
    try:
        _sensor_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _sensor_proc.kill()
    _sensor_proc = None
    return {"ok": True, "status": "stopped"}


@app.get("/sensors/config")
def get_sensor_config():
    try:
        with open(SENSOR_CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@app.put("/sensors/config")
def update_sensor_config(body: dict):
    try:
        with open(SENSOR_CONFIG_PATH, "r") as f:
            current = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        current = {}
    current.update(body)
    with open(SENSOR_CONFIG_PATH, "w") as f:
        json.dump(current, f, indent=2)
    return current


# ════════════════════════════════════════════════════════════════════
# WEBSOCKET
# ════════════════════════════════════════════════════════════════════
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await session.add_client(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        session.remove_client(ws)





@app.get('/CSV/')
def list_files():
    # Get all file names in the directory
    print('help')
    try:
        files = os.listdir(STORAGE_PATH)
        return files
    except FileNotFoundError:
        return {"error": "Directory not found"}, 404


@app.get('/ML/')
async def read_user_item(file: str):
##seperate pd.read function from app.py later
    print(file)
    try:
        
        df = pd.read_csv(STORAGE_PATH + '/'  + file )
        columns = df.columns.to_list()
        return columns
    except:
        print('test for multiple file types')
    try:
        df = pd.read_excel(STORAGE_PATH + '/' + file)
        columns = df.columns.to_list()
        return columns
    except:
        return {"error": "Invalid file type"}, 400
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


