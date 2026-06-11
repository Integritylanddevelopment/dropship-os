#!/usr/bin/env python3
"""
prometheus.py — Prometheus Engine CLI
======================================
One command to run, watch, and manage your AI video pipeline.

USAGE:
  python prometheus.py run                              # run with defaults
  python prometheus.py run "Posture Corrector" fitness # custom product
  python prometheus.py run "Knee Brace" fitness --no-music --no-voice
  python prometheus.py watch                            # watch current run live
  python prometheus.py status                           # tool + service health
  python prometheus.py history                          # last 10 runs
  python prometheus.py open                             # open output folder
  python prometheus.py clean                            # delete old outputs
"""

import os, sys, json, time, shutil, subprocess, argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
LOG_FILE   = BASE_DIR / "prometheus_run.log"
ERR_FILE   = BASE_DIR / "prometheus_run_err.log"
OUTPUT_DIR = BASE_DIR / "prometheus_output"
ENGINE     = BASE_DIR / "prometheus_engine.py"
ENV_FILE   = BASE_DIR / ".env"

FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    r"C:\Users\integ\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1.1-full_build\bin"
)

# ── ANSI colors (Windows-safe) ────────────────────────────────────────────────
class C:
    R = "\033[0m";  BOLD = "\033[1m";  DIM = "\033[2m"
    GREEN = "\033[92m";  YELLOW = "\033[93m";  RED = "\033[91m"
    CYAN = "\033[96m";   BLUE = "\033[94m";    MAG = "\033[95m"
    WHITE = "\033[97m"

def ansi_on():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)

def color(line: str) -> str:
    l = line.lower()
    if any(x in l for x in ["[ok]", "succeeded", "saved", "done", "complete", "mixed"]):
        return C.GREEN + line + C.R
    if any(x in l for x in ["[warn]", "warn", "fallback", "short response"]):
        return C.YELLOW + line + C.R
    if any(x in l for x in ["error", "failed", "traceback", "exception", "[errno]"]):
        return C.RED + line + C.R
    if any(x in l for x in ["running", "submitted", "generating", "step", "cutting"]):
        return C.CYAN + line + C.R
    if any(x in l for x in ["prometheus creation", "===", "---"]):
        return C.MAG + C.BOLD + line + C.R
    if any(x in l for x in ["[fire]", "[list]", "[script]", "[video]", "[mic]",
                              "[music]", "[mix]", "[cut]", "[folder]"]):
        return C.BLUE + line + C.R
    return line

def divider(char="─", w=62):
    print(C.DIM + char * w + C.R)

# ── .env loader ───────────────────────────────────────────────────────────────
def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# ── RUN ───────────────────────────────────────────────────────────────────────
def cmd_run(args):
    product = args.product or "Pet Lint Roller Pro"
    niche   = args.niche   or "pet accessories"

    engine_args = ["--product", product, "--niche", niche]
    if not args.no_voice:  engine_args.append("--voiceover")
    if not args.no_music:  engine_args.append("--music")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["PATH"] = env.get("PATH", "") + ";" + FFMPEG_PATH

    print(f"\n{C.MAG}{C.BOLD}{'='*62}{C.R}")
    print(f"{C.MAG}{C.BOLD}  PROMETHEUS  —  {product}{C.R}")
    print(f"{C.MAG}{C.BOLD}  Niche: {niche}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}{C.R}")
    print(f"{C.MAG}{C.BOLD}{'='*62}{C.R}\n")

    log = open(LOG_FILE, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(ENGINE)] + engine_args,
        env=env, cwd=str(BASE_DIR),
        stdout=log, stderr=log
    )

    print(f"{C.CYAN}Running... (PID {proc.pid})  watching log live{C.R}\n")
    _tail_log(proc)
    log.close()

    rc = proc.returncode
    print()
    divider()
    if rc == 0:
        print(f"{C.GREEN}{C.BOLD}  Pipeline complete! Clips in:{C.R}")
        print(f"  {OUTPUT_DIR}")
    else:
        print(f"{C.RED}{C.BOLD}  Pipeline exited with code {rc}{C.R}")
        print(f"  Check: {LOG_FILE}")
    divider()

def _tail_log(proc):
    """Stream log file to console while proc runs."""
    seen = 0
    while proc.poll() is None:
        try:
            text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            for line in lines[seen:]:
                print(color(line))
            seen = len(lines)
        except Exception:
            pass
        time.sleep(0.4)
    # Flush remainder
    try:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines()[seen:]:
            print(color(line))
    except Exception:
        pass

# ── WATCH ─────────────────────────────────────────────────────────────────────
def cmd_watch(_args):
    if not LOG_FILE.exists():
        print(f"{C.YELLOW}No log yet — run 'python prometheus.py run' first.{C.R}")
        return
    print(f"{C.CYAN}Watching {LOG_FILE.name} (Ctrl+C to stop){C.R}\n")
    seen = 0
    try:
        while True:
            text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            for line in lines[seen:]:
                print(color(line))
            seen = len(lines)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{C.DIM}Watch stopped.{C.R}")

# ── STATUS ────────────────────────────────────────────────────────────────────
def cmd_status(_args):
    load_env()
    print(f"\n{C.BOLD}  Prometheus — Service Status{C.R}")
    divider()

    checks = {}

    # ffmpeg
    checks["ffmpeg"] = shutil.which("ffmpeg") is not None or Path(FFMPEG_PATH, "ffmpeg.exe").exists()

    # whisper
    try:
        import whisper; checks["whisper"] = True
    except ImportError:
        checks["whisper"] = False

    # Quinn
    try:
        import urllib.request
        _bridge_port = os.getenv("QUINN_BRIDGE_PORT", "8765")
        quinn_url    = os.getenv("QUINN_URL", f"http://localhost:{_bridge_port}/chat")
        quinn_secret = os.getenv("QUINN_BRIDGE_SECRET", "")
        data = json.dumps({"message": "ping", "collection": "dropship_intel"}).encode()
        req  = urllib.request.Request(quinn_url, data=data,
               headers={"Authorization": f"Bearer {quinn_secret}",
                        "Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=4)
        checks["quinn"] = True
    except Exception:
        checks["quinn"] = False

    # API keys
    checks["runway"]     = bool(os.getenv("RUNWAY_API_KEY"))
    checks["elevenlabs"] = bool(os.getenv("ELEVENLABS_API_KEY"))
    checks["heygen"]     = bool(os.getenv("HEYGEN_API_KEY"))

    for name, ok in checks.items():
        icon  = f"{C.GREEN}[OK]  {C.R}" if ok else f"{C.YELLOW}[---] {C.R}"
        label = name.ljust(14)
        print(f"  {icon} {label}")

    divider()
    # Output dir stats
    if OUTPUT_DIR.exists():
        clips = list(OUTPUT_DIR.glob("*.mp4"))
        print(f"  Output clips : {C.CYAN}{len(clips)}{C.R}")
        if clips:
            newest = max(clips, key=lambda f: f.stat().st_mtime)
            age    = time.time() - newest.stat().st_mtime
            h, m   = divmod(int(age)//60, 60)
            print(f"  Latest clip  : {C.DIM}{newest.name}{C.R}  ({h}h {m}m ago)")
    divider()
    print()

# ── HISTORY ───────────────────────────────────────────────────────────────────
def cmd_history(_args):
    manifests = sorted(OUTPUT_DIR.glob("manifest_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not manifests:
        print(f"{C.YELLOW}No run history found.{C.R}")
        return

    print(f"\n{C.BOLD}  Prometheus Run History  (latest first){C.R}")
    divider()
    for mf in manifests[:10]:
        try:
            data    = json.loads(mf.read_text(encoding="utf-8"))
            product = data.get("product_name", "?")
            ts      = data.get("generated_at", "?")[:16].replace("T", "  ")
            clips   = data.get("clips", {})
            n       = len(clips)
            print(f"  {C.CYAN}{ts}{C.R}  {C.WHITE}{product}{C.R}  → {n} clips")
        except Exception:
            print(f"  {C.DIM}{mf.name}{C.R}")
    divider()
    print()

# ── OPEN ──────────────────────────────────────────────────────────────────────
def cmd_open(_args):
    if not OUTPUT_DIR.exists():
        print(f"{C.YELLOW}Output folder doesn't exist yet.{C.R}")
        return
    print(f"{C.CYAN}Opening {OUTPUT_DIR}{C.R}")
    os.startfile(str(OUTPUT_DIR))

# ── CLEAN ─────────────────────────────────────────────────────────────────────
def cmd_clean(_args):
    if not OUTPUT_DIR.exists():
        print("Nothing to clean.")
        return
    files = list(OUTPUT_DIR.iterdir())
    print(f"{C.YELLOW}Delete {len(files)} files in {OUTPUT_DIR}? [y/N] {C.R}", end="")
    if input().strip().lower() == "y":
        shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir()
        print(f"{C.GREEN}Cleaned.{C.R}")
    else:
        print("Cancelled.")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    ansi_on()
    load_env()

    p = argparse.ArgumentParser(
        prog="prometheus",
        description="Prometheus AI Video Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  run       [product] [niche]   Generate videos (default: Pet Lint Roller Pro)
  watch                         Stream live log output
  status                        Check tools and API keys
  history                       Show last 10 runs
  open                          Open output folder in Explorer
  clean                         Delete all output files
        """
    )
    sub = p.add_subparsers(dest="cmd")

    # run
    r = sub.add_parser("run", help="Run the pipeline")
    r.add_argument("product", nargs="?", default=None, help="Product name")
    r.add_argument("niche",   nargs="?", default=None, help="Product niche")
    r.add_argument("--no-voice", action="store_true", help="Skip voiceover")
    r.add_argument("--no-music", action="store_true", help="Skip music")

    # watch / status / history / open / clean
    sub.add_parser("watch",   help="Watch live log")
    sub.add_parser("status",  help="Service health check")
    sub.add_parser("history", help="Run history")
    sub.add_parser("open",    help="Open output folder")
    sub.add_parser("clean",   help="Delete outputs")

    args = p.parse_args()

    dispatch = {
        "run":     cmd_run,
        "watch":   cmd_watch,
        "status":  cmd_status,
        "history": cmd_history,
        "open":    cmd_open,
        "clean":   cmd_clean,
    }

    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
