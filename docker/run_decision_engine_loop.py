"""run_decision_engine_loop.py - runs the Decision Engine on a fixed interval inside its container.
Lives inside the always-on stack (no Windows scheduled tasks) per Alex 2026-07-12.
"""
import os
import subprocess
import sys
import time

INTERVAL = int(os.environ.get("DECISION_ENGINE_INTERVAL_SEC", "86400"))

while True:
    print("[decision-engine-loop] starting run", flush=True)
    try:
        r = subprocess.run([sys.executable, "engines/decision_engine.py"], cwd="/app", timeout=3600)
        print("[decision-engine-loop] run finished rc=" + str(r.returncode), flush=True)
    except Exception as e:
        print("[decision-engine-loop] run failed: " + str(e), flush=True)
    time.sleep(INTERVAL)
