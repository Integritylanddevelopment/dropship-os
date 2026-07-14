"""LAUNCH_SHIPSTACK.pyw - One-click ShipStack stack launcher (Docker edition).

Rewritten 2026-07-12: ShipStack services now run as Docker containers on ALIEN
(100.66.135.31). This launcher:
  1. Ensures the compose stack is up on ALIEN (kill-before-launch is handled by
     Docker: compose reconciles, restart=unless-stopped keeps it always-on).
  2. Waits for each service health endpoint in dependency order.
  3. Runs tests/verify_stack.py and shows a summary popup.

Containers (always-on): shipstack-engine :8889, prometheus-engine :8766,
social-ai-agent :8867, shipstack-dashboard :8890, pipeline-dashboard :8891,
decision-engine (loop), content-pipeline (loop).
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ALIEN = "100.66.135.31"
CRED = r"C:\Users\integ\quinn-proxy\alienware_cred.xml"
SHIPSTACK_DIR = Path(r"C:\Users\integ\Documents\Claude\Projects\ShipStack")
LOG_FILE = SHIPSTACK_DIR / "logs" / "launcher_shipstack.log"
CREATE_NO_WINDOW = 0x08000000

# Health checks in dependency order: engine first, then dependents.
CHECKS = [
    ("ShipStack Engine",    f"http://{ALIEN}:8889/health", 90),
    ("Prometheus Engine",   f"http://{ALIEN}:8766/health", 60),
    ("Social AI Agent",     f"http://{ALIEN}:8867/health", 60),
    ("ShipStack Dashboard", f"http://{ALIEN}:8890/",       60),
    ("Pipeline Dashboard",  f"http://{ALIEN}:8891/",       60),
]

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " | " + msg + "\n")

def compose_up():
    ps = (
        "$cred = Import-CliXml '" + CRED + "'; "
        "Invoke-Command -ComputerName " + ALIEN + " -Credential $cred -ScriptBlock { "
        "Set-Location C:\\shipstack; "
        "docker compose -f docker-compose.shipstack.yml up -d --no-build 2>&1 | Out-String } "
    )
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=600,
                       creationflags=CREATE_NO_WINDOW)
    log("compose up rc=" + str(r.returncode))
    return r.returncode == 0

def wait_health(url, timeout_sec):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "launcher"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False

def run_verify():
    py = sys.executable.replace("pythonw.exe", "python.exe")
    vs = SHIPSTACK_DIR / "tests" / "verify_stack.py"
    if not vs.exists():
        return "verify_stack.py not found"
    try:
        r = subprocess.run([py, str(vs)], capture_output=True, text=True,
                           timeout=120, creationflags=CREATE_NO_WINDOW,
                           cwd=str(SHIPSTACK_DIR))
        log("verify_stack output:\n" + (r.stdout or "") + (r.stderr or ""))
        return r.stdout or r.stderr or "no output"
    except Exception as e:
        return "verify failed: " + str(e)

def popup(title, text):
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        root = tk.Tk()
        root.title(title)
        root.geometry("560x420")
        box = scrolledtext.ScrolledText(root, wrap="word", font=("Consolas", 10))
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True)
        tk.Button(root, text="Close", command=root.destroy).pack(pady=6)
        root.attributes("-topmost", True)
        root.mainloop()
    except Exception:
        pass

def main():
    log("=" * 50)
    log("ShipStack launch (Docker on ALIEN)")
    lines = []
    ok = compose_up()
    lines.append(("[OK]" if ok else "[WARN]") + " compose up on ALIEN")
    all_healthy = True
    for name, url, tmo in CHECKS:
        good = wait_health(url, tmo)
        all_healthy = all_healthy and good
        line = ("[OK] " if good else "[FAIL] ") + name + "  " + url
        lines.append(line)
        log(line)
    lines.append("")
    lines.append("--- verify_stack.py ---")
    lines.append(run_verify())
    status = "HEALTHY" if all_healthy else "PROBLEMS FOUND"
    log("result: " + status)
    try:
        os.startfile(f"http://{ALIEN}:8890/")
    except Exception:
        pass
    popup("ShipStack " + status, "\n".join(lines))

if __name__ == "__main__":
    main()