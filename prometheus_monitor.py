#!/usr/bin/env python3
"""
prometheus_monitor.py — Prometheus Engine Live Monitor
=======================================================
Watch a Prometheus run in real-time with color-coded status.

USAGE:
  python prometheus_monitor.py             # watch current run
  python prometheus_monitor.py --run       # launch + watch
  python prometheus_monitor.py --product "Posture Corrector" --niche "fitness" --run
  python prometheus_monitor.py --history   # show last 5 runs
  python prometheus_monitor.py --open      # open output folder
"""

import os
import sys
import time
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# -- Config ------------------------------------------------------------------
BASE_DIR   = Path(__file__).parent
LOG_FILE   = BASE_DIR / "prometheus_run.log"
OUTPUT_DIR = BASE_DIR / "prometheus_output"
BAT_FILE   = BASE_DIR / "RUN_PROMETHEUS_NOW.bat"

# -- Colors (Windows-safe ANSI) ----------------------------------------------
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    DIM    = "\033[2m"
    BLUE   = "\033[94m"
    MAGENTA = "\033[95m"

def enable_ansi():
    """Enable ANSI colors on Windows."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

def color_line(line: str) -> str:
    """Apply color coding to a log line."""
    l = line.strip()
    if not l:
        return ""

    # Status badges
    if "[OK]" in l or "SUCCEEDED" in l or "Pipeline complete" in l or "Exit code: 0" in l:
        return f"{C.GREEN}{l}{C.RESET}"
    if "[ERROR]" in l or "FAILED" in l or "Exit code: 1" in l:
        return f"{C.RED}{l}{C.RESET}"
    if "[WARN]" in l or "THROTTLED" in l:
        return f"{C.YELLOW}{l}{C.RESET}"
    if "RUNNING" in l:
        return f"{C.CYAN}{l}{C.RESET}"
    if "[DONE]" in l or "downloaded" in l:
        return f"{C.GREEN}{C.BOLD}{l}{C.RESET}"

    # Step headers
    if "[VIDEO]" in l:  return f"{C.MAGENTA}{C.BOLD}{l}{C.RESET}"
    if "[SCRIPT]" in l: return f"{C.BLUE}{l}{C.RESET}"
    if "[MIC]" in l:    return f"{C.CYAN}{l}{C.RESET}"
    if "[MUSIC]" in l:  return f"{C.CYAN}{l}{C.RESET}"
    if "[CUT]" in l:    return f"{C.BLUE}{l}{C.RESET}"
    if "[MIX]" in l:    return f"{C.CYAN}{l}{C.RESET}"
    if "[LIST]" in l:   return f"{C.WHITE}{l}{C.RESET}"
    if "[FIRE]" in l:   return f"{C.MAGENTA}{C.BOLD}{l}{C.RESET}"
    if "====" in l:     return f"{C.BOLD}{l}{C.RESET}"

    # Section labels
    if l.startswith("   TikTok") or l.startswith("   Instagram") or \
       l.startswith("   YouTube") or l.startswith("   Pinterest") or \
       l.startswith("   Facebook") or l.startswith("   X /"):
        return f"{C.GREEN}  {l}{C.RESET}"

    return f"{C.DIM}{l}{C.RESET}"

def print_header():
    print(f"\n{C.BOLD}{C.MAGENTA}{'='*60}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}  PROMETHEUS MONITOR{C.RESET}")
    print(f"{C.DIM}  {BASE_DIR}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}{'='*60}{C.RESET}\n")

def watch_log(follow: bool = True):
    """Stream prometheus_run.log with color coding."""
    if not LOG_FILE.exists():
        print(f"{C.YELLOW}Waiting for log file...{C.RESET}")
        while not LOG_FILE.exists():
            time.sleep(0.5)

    seen_lines = 0
    done = False

    print(f"{C.DIM}[Monitor] Watching {LOG_FILE.name}{C.RESET}\n")

    while True:
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            time.sleep(0.5)
            continue

        for line in lines[seen_lines:]:
            colored = color_line(line)
            if colored:
                print(colored)
            seen_lines += 1

            # Detect completion
            if "Exit code:" in line:
                done = True

        if done and not follow:
            break

        if done:
            print(f"\n{C.GREEN}{C.BOLD}[Monitor] Run complete.{C.RESET}")
            show_outputs()
            break

        time.sleep(0.5)

def show_outputs():
    """List the most recently generated clips."""
    if not OUTPUT_DIR.exists():
        return

    # Find newest run folder
    run_dirs = sorted(
        [d for d in OUTPUT_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True
    )

    # Also check for loose files
    clips = sorted(OUTPUT_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    if run_dirs:
        clips = list(run_dirs[0].glob("*.mp4")) + clips

    if not clips:
        print(f"{C.YELLOW}No clips found in output directory.{C.RESET}")
        return

    print(f"\n{C.BOLD}{C.WHITE}Output clips:{C.RESET}")
    for clip in clips[:12]:
        size_kb = clip.stat().st_size // 1024
        print(f"  {C.GREEN}[OK]{C.RESET}  {clip.name}  {C.DIM}({size_kb} KB){C.RESET}")

    print(f"\n{C.DIM}Folder: {OUTPUT_DIR}{C.RESET}")

def show_history():
    """Show last 5 run summaries from output manifests."""
    if not OUTPUT_DIR.exists():
        print(f"{C.YELLOW}No output directory found.{C.RESET}")
        return

    manifests = sorted(OUTPUT_DIR.glob("manifest_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not manifests:
        print(f"{C.YELLOW}No run history found.{C.RESET}")
        return

    print(f"\n{C.BOLD}Last {min(5, len(manifests))} runs:{C.RESET}\n")
    import json
    for m in manifests[:5]:
        try:
            data = json.loads(m.read_text())
            ts = data.get("generated_at", "unknown time")
            product = data.get("product", "unknown product")
            clips = data.get("clips", {})
            n = len(clips)
            print(f"  {C.CYAN}{ts}{C.RESET}  {C.BOLD}{product}{C.RESET}  {C.GREEN}{n} clips{C.RESET}")
        except Exception:
            print(f"  {C.DIM}{m.name}{C.RESET}")

def launch_and_watch(product: str = None, niche: str = None):
    """Update bat file if product/niche given, then launch and watch."""
    if product or niche:
        bat = BAT_FILE.read_text(encoding="utf-8")
        import re
        if product:
            bat = re.sub(r'--product "[^"]*"', f'--product "{product}"', bat)
        if niche:
            bat = re.sub(r'--niche "[^"]*"', f'--niche "{niche}"', bat)
        BAT_FILE.write_text(bat, encoding="utf-8")
        print(f"{C.GREEN}Updated bat: product={product or '(unchanged)'}, niche={niche or '(unchanged)'}{C.RESET}")

    print(f"{C.CYAN}Launching Prometheus...{C.RESET}")
    subprocess.Popen(
        [str(BAT_FILE)],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    time.sleep(2)
    watch_log()

def open_output():
    """Open output folder in Explorer."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    subprocess.run(["explorer", str(OUTPUT_DIR)])

# -- Main --------------------------------------------------------------------
def main():
    enable_ansi()
    print_header()

    parser = argparse.ArgumentParser(description="Prometheus Engine Monitor")
    parser.add_argument("--run",     action="store_true", help="Launch Prometheus then watch")
    parser.add_argument("--watch",   action="store_true", help="Watch current run (default)")
    parser.add_argument("--history", action="store_true", help="Show run history")
    parser.add_argument("--open",    action="store_true", help="Open output folder")
    parser.add_argument("--product", type=str, help="Product name (use with --run)")
    parser.add_argument("--niche",   type=str, help="Product niche (use with --run)")
    args = parser.parse_args()

    if args.history:
        show_history()
    elif args.open:
        open_output()
    elif args.run:
        launch_and_watch(product=args.product, niche=args.niche)
    else:
        # Default: watch log
        watch_log()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.DIM}[Monitor] Stopped.{C.RESET}")
