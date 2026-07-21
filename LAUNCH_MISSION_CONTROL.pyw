"""LAUNCH_MISSION_CONTROL.pyw — One double-click: services up + browser open.

Starts the LOCAL ShipStack stack (latest code) and opens Mission Control:
  1. Kill stale local listeners on 8889 / 8867 / 8766 (kill-before-launch).
  2. Start ShipStack Engine, Social AI Agent, Prometheus Engine (hidden windows).
  3. Wait for health endpoints.
  4. Open http://127.0.0.1:8889/ — the Mission Control UI.

No console windows. Logs to logs/launcher_mission_control.log.
"""
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\integ\Documents\Claude\Projects\ShipStack")
LOG_FILE = ROOT / "logs" / "launcher_mission_control.log"
PYTHON = sys.executable.replace("pythonw.exe", "python.exe")
CREATE_NO_WINDOW = 0x08000000

SERVICES = [
    ("ShipStack Engine", ROOT / "engines" / "shipstack_engine.py", 8889),
    ("Social AI Agent",  ROOT / "agents" / "social_ai_agent.py",  8867),
    ("Prometheus Engine", ROOT / "engines" / "prometheus_engine.py", 8766),
]

UI_URL = "http://127.0.0.1:8889/"


def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " | " + msg + "\n")


def kill_port(port):
    """Kill any local process listening on the port (kill-before-launch)."""
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True,
            timeout=15, creationflags=CREATE_NO_WINDOW,
        ).stdout
        pids = set()
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                m = re.search(r"(\d+)\s*$", line)
                if m:
                    pids.add(m.group(1))
        for pid in pids:
            if pid == "0":
                continue
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, timeout=10,
                           creationflags=CREATE_NO_WINDOW)
            log(f"killed PID {pid} on :{port}")
    except Exception as e:
        log(f"kill_port {port} error: {e}")


def start_service(name, script, port):
    if not script.exists():
        log(f"MISSING: {script}")
        return
    subprocess.Popen(
        [PYTHON, str(script)],
        cwd=str(ROOT),
        creationflags=CREATE_NO_WINDOW,
        stdout=open(ROOT / "logs" / f"svc_{port}.log", "a", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
    )
    log(f"started {name} :{port}")


def wait_health(port, timeout_sec=60):
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "launcher"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def main():
    log("=" * 50)
    log("Mission Control launch (local stack)")

    for _, _, port in SERVICES:
        kill_port(port)
    time.sleep(1)

    for name, script, port in SERVICES:
        start_service(name, script, port)

    results = []
    for name, _, port in SERVICES:
        ok = wait_health(port)
        results.append(f"{'[OK]' if ok else '[FAIL]'} {name} :{port}")
        log(results[-1])

    # Open the UI regardless — engine is the one that matters
    try:
        os.startfile(UI_URL)
        log(f"opened {UI_URL}")
    except Exception as e:
        log(f"browser open failed: {e}")


if __name__ == "__main__":
    main()
