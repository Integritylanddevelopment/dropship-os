#!/usr/bin/env python3
"""
shipstack.py — ShipStack AI Unified CLI
========================================
One script to run everything.

Usage:
  python shipstack.py onboard "Product Name" [zendrop_id]
  python shipstack.py schedule [--dry-run]
  python shipstack.py status
  python shipstack.py calendar [product-slug]
  python shipstack.py engine [--port 8889]
  python shipstack.py quinn [--port 8765]
  python shipstack.py verify
  python shipstack.py help
"""

import sys
import os
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# ── Helpers ───────────────────────────────────────────────────────────────

def _python():
    """Return the best available Python executable."""
    venv = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    return sys.executable

def _run(script: Path, *args):
    """Run a Python script as a subprocess and stream output."""
    cmd = [_python(), str(script)] + list(args)
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    return result.returncode

def _header(title: str):
    width = 52
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)

def _ok(msg):  print(f"  ✅  {msg}")
def _warn(msg): print(f"  ⚠️  {msg}")
def _err(msg):  print(f"  ❌  {msg}")

# ── Commands ──────────────────────────────────────────────────────────────

def cmd_onboard(args):
    """
    onboard "Product Name" [zendrop_id]
    Run the full 4-step product onboarding pipeline:
      A. Zendrop pull  B. Collateral scrape
      C. Quinn copy    D. Prometheus manifest + content calendar
    """
    if not args:
        _err("Product name required.")
        print("  Usage: python shipstack.py onboard \"Product Name\" [zendrop_id]")
        return 1

    product_name = args[0]
    extra        = args[1:]   # optional zendrop_id

    _header(f"Onboarding: {product_name}")
    script = BASE_DIR / "agents" / "product_onboarding_agent.py"
    return _run(script, product_name, *extra)


def cmd_schedule(args):
    """
    schedule [--dry-run]
    Dispatch all posts that are due right now (Kamil's 7am/12pm/8pm CT windows).
    --dry-run  Preview without actually dispatching.
    """
    _header("Post Scheduler")
    script = BASE_DIR / "agents" / "post_scheduler.py"
    flags  = ["--dry-run"] if "--dry-run" in args else []
    return _run(script, *flags)


def cmd_status(args):
    """
    status
    Show per-product content calendar stats: queued / sent / failed by platform.
    """
    _header("Calendar Status")
    script = BASE_DIR / "agents" / "post_scheduler.py"
    return _run(script, "--status")


def cmd_calendar(args):
    """
    calendar [product-slug]
    Print the content calendar for a product (or list all products).
    """
    _header("Content Calendar")
    collateral = BASE_DIR / "data" / "product_collateral"

    if not collateral.exists():
        _warn("No product_collateral directory found yet. Run onboard first.")
        return 1

    slug = args[0] if args else None
    calendars = list(collateral.glob("*/content_calendar.json"))

    if not calendars:
        _warn("No calendars found. Run onboard to generate one.")
        return 1

    if slug:
        calendars = [c for c in calendars if c.parent.name == slug]
        if not calendars:
            _err(f"No calendar found for slug: {slug}")
            print(f"  Available: {[c.parent.name for c in collateral.glob('*/content_calendar.json')]}")
            return 1

    for cal_path in calendars:
        data     = json.loads(cal_path.read_text(encoding="utf-8"))
        product  = data.get("product", cal_path.parent.name)
        posts    = data.get("posts", [])
        queued   = sum(1 for p in posts if p.get("status") == "queued")
        sent     = sum(1 for p in posts if p.get("status") == "sent")
        failed   = sum(1 for p in posts if p.get("status") == "failed")
        summary  = data.get("summary", {})

        print(f"\n  Product  : {product}")
        print(f"  Slug     : {cal_path.parent.name}")
        print(f"  Total    : {len(posts)} posts over 30 days")
        print(f"  Queued   : {queued}  |  Sent: {sent}  |  Failed: {failed}")
        if summary:
            print(f"  TikTok   : {summary.get('tiktok', 0)}")
            print(f"  Instagram: {summary.get('instagram', 0)}")
            print(f"  YouTube  : {summary.get('youtube', 0)}")
        print(f"  File     : {cal_path}")

        # Show next 5 queued posts
        upcoming = [p for p in posts if p.get("status") == "queued"][:5]
        if upcoming:
            print(f"\n  Next {len(upcoming)} queued posts:")
            for p in upcoming:
                hook = (p.get("script") or p.get("caption") or "")[:60]
                print(f"    Day {p['day']:>2} {p['date']} {p['time']}  [{p['platform'].upper():<10}]  {hook}...")
    return 0


def cmd_engine(args):
    """
    engine [--port PORT]
    Start the ShipStack HTTP engine (default port 8889).
    Dashboard: http://localhost:8889
    """
    port = "8889"
    for i, a in enumerate(args):
        if a == "--port" and i + 1 < len(args):
            port = args[i + 1]

    _header(f"ShipStack Engine  →  http://localhost:{port}")
    script = BASE_DIR / "shipstack_engine.py"
    if not script.exists():
        _err("shipstack_engine.py not found.")
        return 1

    env = os.environ.copy()
    env["SHIPSTACK_PORT"] = port
    cmd = [_python(), str(script)]
    print(f"  Starting engine on port {port}  (Ctrl+C to stop)\n")
    try:
        subprocess.run(cmd, cwd=str(BASE_DIR), env=env)
    except KeyboardInterrupt:
        print("\n  Engine stopped.")
    return 0


def cmd_quinn(args):
    """
    quinn [--port PORT]
    Launch the Quinn copy server (default port 8765).
    Reads from LAUNCH_QUINN_SERVER.ps1 or falls back to Ollama.
    """
    _header("Quinn Copy Server")
    ps1 = BASE_DIR / "LAUNCH_QUINN_SERVER.ps1"
    if ps1.exists():
        print("  Launching via LAUNCH_QUINN_SERVER.ps1 ...")
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                       cwd=str(BASE_DIR))
    else:
        _warn("LAUNCH_QUINN_SERVER.ps1 not found.")
        print("  Falling back — ensure Ollama is running on port 11434.")
    return 0


def cmd_verify(args):
    """
    verify
    Check that all required services, files, and env vars are in place.
    """
    _header("ShipStack Verify")
    script = BASE_DIR / "verify_stack.py"
    if script.exists():
        return _run(script)

    # Built-in quick check
    import importlib, urllib.request

    checks = {
        ".env exists":                  (BASE_DIR / ".env").exists(),
        "agents/product_onboarding_agent.py": (BASE_DIR / "agents" / "product_onboarding_agent.py").exists(),
        "agents/content_calendar_builder.py": (BASE_DIR / "agents" / "content_calendar_builder.py").exists(),
        "agents/post_scheduler.py":     (BASE_DIR / "agents" / "post_scheduler.py").exists(),
        "agents/advisors/hormozi.json": (BASE_DIR / "agents" / "advisors" / "hormozi.json").exists(),
        "agents/advisors/garyvee.json": (BASE_DIR / "agents" / "advisors" / "garyvee.json").exists(),
        "agents/advisors/kamil.json":   (BASE_DIR / "agents" / "advisors" / "kamil.json").exists(),
        "shipstack_engine.py":          (BASE_DIR / "shipstack_engine.py").exists(),
        "dropship-os/calendar.html":    (BASE_DIR / "dropship-os" / "calendar.html").exists(),
        "data/ directory":              (BASE_DIR / "data").exists(),
    }

    for label, ok in checks.items():
        if ok: _ok(label)
        else:  _err(label)

    # Service checks
    print()
    _quinn_port   = int(os.getenv("QUINN_BRIDGE_PORT", "8765"))
    _engine_port  = int(os.getenv("SHIPSTACK_PORT", "8889"))
    _ollama_port  = int(os.getenv("OLLAMA_PORT", "11434"))
    for name, port in [("Quinn", _quinn_port), ("ShipStack Engine", _engine_port), ("Ollama", _ollama_port)]:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
            _ok(f"{name} online  (:{port})")
        except Exception:
            _warn(f"{name} offline (:{port})")

    return 0


def cmd_help(args):
    """
    help
    Show all available commands.
    """
    _header("ShipStack CLI — Commands")
    commands = {
        "onboard":  'python shipstack.py onboard "Product Name" [zendrop_id]',
        "schedule": "python shipstack.py schedule [--dry-run]",
        "status":   "python shipstack.py status",
        "calendar": "python shipstack.py calendar [product-slug]",
        "engine":   "python shipstack.py engine [--port 8889]",
        "quinn":    "python shipstack.py quinn",
        "verify":   "python shipstack.py verify",
        "help":     "python shipstack.py help",
    }
    descriptions = {
        "onboard":  "Full 4-step product onboarding (Zendrop → Scrape → Quinn → Prometheus)",
        "schedule": "Dispatch posts due now (Kamil's 7am/12pm/8pm CT windows)",
        "status":   "Show queued/sent/failed counts for all products",
        "calendar": "Print content calendar details and upcoming posts",
        "engine":   "Start the ShipStack HTTP engine + dashboard",
        "quinn":    "Launch Quinn copy server",
        "verify":   "Check all files, env vars, and services",
        "help":     "Show this message",
    }
    for cmd, usage in commands.items():
        print(f"\n  {cmd}")
        print(f"    {descriptions[cmd]}")
        print(f"    {usage}")
    print()
    return 0


# ── Router ────────────────────────────────────────────────────────────────

COMMANDS = {
    "onboard":  cmd_onboard,
    "schedule": cmd_schedule,
    "status":   cmd_status,
    "calendar": cmd_calendar,
    "engine":   cmd_engine,
    "quinn":    cmd_quinn,
    "verify":   cmd_verify,
    "help":     cmd_help,
}

def main():
    argv = sys.argv[1:]
    if not argv:
        cmd_help([])
        return

    cmd = argv[0].lower()
    args = argv[1:]

    handler = COMMANDS.get(cmd)
    if not handler:
        _err(f"Unknown command: {cmd}")
        print(f"  Run: python shipstack.py help")
        sys.exit(1)

    code = handler(args)
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
