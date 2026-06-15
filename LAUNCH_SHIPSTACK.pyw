"""LAUNCH_SHIPSTACK.pyw - One-click ShipStack stack launcher.

ShipStack only. Quinn is a separate system and must already be running
(quinn_http_bridge on :8765) before launching ShipStack.

Silent (.pyw - no console window). All child processes spawn hidden.
Shows a brief status popup when launch completes.

Services launched:
  - Prometheus Engine    :8766
  - ShipStack Engine     :8889
  - ShipStack Dashboard  :8890
  - Pipeline Dashboard   :8891
  - Social AI Agent      :8867
"""
import os
import sys
import time
import socket
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Hide our own console window immediately
try:
    import ctypes
    _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if _hwnd:
        ctypes.windll.user32.ShowWindow(_hwnd, 0)
except Exception:
    pass

try:
    from dotenv import load_dotenv
    load_dotenv(Path(r"C:\Users\integ\Documents\Claude\Projects\ShipStack\.env"))
except ImportError:
    pass

# --- Config ----------------------------------------------------------------
SHIPSTACK_DIR = Path(os.environ.get("SHIPSTACK_DIR", r"C:\Users\integ\Documents\Claude\Projects\ShipStack"))
QUINN_DIR     = Path(os.environ.get("QUINN_DIR", r"C:\Users\integ\quinn-proxy"))
LOG_FILE      = SHIPSTACK_DIR / "logs" / "launcher_shipstack.log"

CREATE_NO_WINDOW = 0x08000000

def _pick_python():
    candidates = [
        os.environ.get("PYTHON_EXE"),
        r"C:\Users\integ\AppData\Local\Programs\Python\Python312\pythonw.exe",
        r"C:\Users\integ\AppData\Local\Programs\Python\Python312\python.exe",
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.exists() and p.stat().st_size > 50_000:
            return str(p)
    return r"C:\Users\integ\AppData\Local\Programs\Python\Python312\python.exe"

PYTHON_EXE = _pick_python()

# --- ShipStack services ----------------------------------------------------
SERVICES = [
    {"name": "Prometheus Engine",   "script": SHIPSTACK_DIR / "engines" / "prometheus_engine.py",
     "port": 8766, "health": "http://127.0.0.1:8766/health", "log": "prometheus_engine"},
    {"name": "ShipStack Engine",    "script": SHIPSTACK_DIR / "engines" / "shipstack_engine.py",
     "port": 8889, "health": "http://127.0.0.1:8889/health", "log": "shipstack_engine",
     "fallback": SHIPSTACK_DIR / "engines" / "shipstack_engine_minimal.py"},
    {"name": "ShipStack Dashboard", "script": SHIPSTACK_DIR / "engines" / "shipstack_dashboard.py",
     "port": 8890, "health": "http://127.0.0.1:8890/", "log": "shipstack_dashboard",
     "fallback": SHIPSTACK_DIR / "engines" / "shipstack_dashboard_minimal.py"},
    {"name": "Pipeline Dashboard",  "script": SHIPSTACK_DIR / "dashboard" / "pipeline_dashboard.py",
     "port": 8891, "health": "http://127.0.0.1:8891/", "log": "pipeline_dashboard"},
    {"name": "Social AI Agent",     "script": SHIPSTACK_DIR / "agents" / "social_ai_agent.py",
     "port": 8867, "health": "http://127.0.0.1:8867/health", "log": "social_ai_agent",
     "fallback": SHIPSTACK_DIR / "social_ai_agent" / "main.py"},
]

RESULTS = []

# --- Helpers ---------------------------------------------------------------
def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def url_responds(url, timeout=2):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 500
    except urllib.error.HTTPError as e:
        return 400 <= e.code < 500
    except Exception:
        return False

def wait_for_http(url, timeout_sec=30):
    start = time.time()
    deadline = start + timeout_sec
    while time.time() < deadline:
        if url_responds(url, timeout=1):
            return True, time.time() - start
        time.sleep(0.5)
    return False, time.time() - start

def kill_port(port):
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -EA SilentlyContinue | "
             f"Where-Object {{ $_.State -eq 'Listen' }} | "
             f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }}"],
            capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        pass

def kill_stale_python(script_name):
    safe = script_name.replace("'", "''")
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{safe}*' "
             f"-and ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') }} | "
             f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }}"],
            capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        pass

def launch_service(svc):
    name = svc["name"]
    script = svc.get("script")
    fallback = svc.get("fallback")
    port = svc.get("port")
    health = svc.get("health")
    log_name = svc.get("log", name.lower().replace(" ", "_"))

    chosen = None
    note = ""
    if script and script.exists():
        chosen = script
    elif fallback and fallback.exists():
        chosen = fallback
        note = f"using fallback={fallback.name}"
    else:
        log(f"SKIP {name}: script not found")
        return False, 0.0, "FILE MISSING"

    if port:
        kill_port(port)
    kill_stale_python(chosen.name)

    log_path = SHIPSTACK_DIR / "logs" / f"{log_name}.log"
    err_path = SHIPSTACK_DIR / "logs" / f"{log_name}.err"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(log_path, "a", encoding="utf-8") as out, open(err_path, "a", encoding="utf-8") as err:
            subprocess.Popen(
                [PYTHON_EXE, str(chosen)],
                cwd=str(SHIPSTACK_DIR),
                stdout=out, stderr=err,
                creationflags=CREATE_NO_WINDOW,
            )
        log(f"STARTED {name}: {chosen}")
    except Exception as e:
        log(f"FAIL {name}: {e}")
        return False, 0.0, f"spawn failed: {e}"

    if health:
        ok, took = wait_for_http(health, timeout_sec=30)
        return ok, took, (note or ("OK" if ok else "health timeout"))

    return True, 0.0, (note or "spawned")

# --- Status popup ----------------------------------------------------------
def show_popup(up, total, down_names, took_total):
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("ShipStack â€” Launch Complete")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.configure(bg="#1a1a2e")

        color = "#4caf50" if up == total else "#ff9800" if up >= total * 0.7 else "#f44336"
        tk.Label(root, text=f"âœ“ {up} / {total} ShipStack services UP",
                 font=("Segoe UI", 13, "bold"), fg=color, bg="#1a1a2e").pack(pady=(12, 4))

        if down_names:
            tk.Label(root, text="Down: " + ", ".join(down_names),
                     font=("Segoe UI", 9), fg="#ff9800", bg="#1a1a2e").pack(padx=16, pady=2)

        tk.Label(root, text=f"Took {took_total:.0f}s",
                 font=("Segoe UI", 9), fg="#888", bg="#1a1a2e").pack(pady=(2, 8))

        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w = max(root.winfo_width(), 340)
        h = max(root.winfo_height(), 120)
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{sh-200}")

        countdown = [8]
        lbl = tk.Label(root, text="Closing in 8sâ€¦", font=("Segoe UI", 8), fg="#555", bg="#1a1a2e")
        lbl.pack(pady=(0, 8))
        def tick():
            countdown[0] -= 1
            if countdown[0] <= 0:
                root.destroy(); return
            lbl.config(text=f"Closing in {countdown[0]}sâ€¦")
            root.after(1000, tick)
        root.after(1000, tick)
        root.mainloop()
    except Exception:
        pass

# --- Main ------------------------------------------------------------------
def main():
    log("=" * 50)
    log("LAUNCH_SHIPSTACK start")

    # Verify Quinn bridge is up before starting ShipStack
    if not url_responds("http://127.0.0.1:8765/health", timeout=3):
        log("WARN: Quinn HTTP Bridge (:8765) not responding â€” ShipStack may not work correctly")

    for svc in SERVICES:
        ok, took, note = launch_service(svc)
        RESULTS.append({"name": svc["name"], "status": "UP" if ok else "DOWN", "took": took, "note": note})

    up = sum(1 for r in RESULTS if r["status"] == "UP")
    down = [r["name"] for r in RESULTS if r["status"] != "UP"]
    total_took = sum(r["took"] for r in RESULTS)

    log("SUMMARY")
    for r in RESULTS:
        log(f"  {r['name']:<28} {r['status']:<5} {r['took']:.1f}s  {r['note']}")
    log(f"UP: {up}/{len(RESULTS)}")
    log("LAUNCH_SHIPSTACK done")
    log("=" * 50)

    show_popup(up, len(RESULTS), down, total_took)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
