"""run_content_pipeline_loop.py - runs the Content Pipeline on a fixed interval inside its container.
Lives inside the always-on stack (no Windows scheduled tasks) per Alex 2026-07-12.
"""
import os
import subprocess
import sys
import time

INTERVAL = int(os.environ.get("CONTENT_PIPELINE_INTERVAL_SEC", "86400"))

while True:
    print("[content-pipeline-loop] starting run", flush=True)
    try:
        r = subprocess.run([sys.executable, "agents/content_pipeline.py"], cwd="/app", timeout=7200)
        print("[content-pipeline-loop] run finished rc=" + str(r.returncode), flush=True)
    except Exception as e:
        print("[content-pipeline-loop] run failed: " + str(e), flush=True)
    time.sleep(INTERVAL)
