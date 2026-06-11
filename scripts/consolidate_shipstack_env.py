#!/usr/bin/env python3
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

"""
consolidate_shipstack_env.py - Merge ShipStack .env files into ONE clean file.

Run from dropship-os/:
  python consolidate_shipstack_env.py --dry-run    # preview, no writes
  python consolidate_shipstack_env.py              # do the merge

What it does:
- Reads parent Drop shipping/.env, dropship-os/.env.local, dropship-os/.env
- Dedupes (later non-blank wins)
- Drops ANTHROPIC_API_KEY and any FALLBACK_API_URL pointing at anthropic.com (Directive #3)
- Forces FALLBACK_ENABLED=false
- Sorts into 17 labeled sections
- Backs up old .env files before overwriting
- Writes .env (real values) and .env.example (blanks)
- Verifies .gitignore covers .env*
"""
import argparse, os, re, shutil
from datetime import datetime
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).parent.resolve()
PARENT = ROOT.parent

SOURCES = [PARENT / ".env", ROOT / ".env.local", ROOT / ".env"]
TARGET_ENV = ROOT / ".env"
TARGET_EX = ROOT / ".env.example"

FORBIDDEN_KEYS = {"ANTHROPIC_API_KEY"}
FORCED = {
    "FALLBACK_ENABLED": "false",
    "APP_PRIMARY_PROFILE": "quinn",
    "APP_SECONDARY_PROFILE": "shipstack",
}
FORBIDDEN_VAL = {"FALLBACK_API_URL": re.compile(r"anthropic\.com", re.I)}

SECTIONS = OrderedDict([
    ("ShipStack Ports", ["PORT", "SHIPSTACK_ENGINE_PORT", "DASHBOARD_PORT", "PROMETHEUS_ENGINE_PORT", "SOCIAL_AI_AGENT_PORT", "SHIPSTACK_DASHBOARD_PORT"]),
    ("Quinn Bridge", ["QUINN_BRIDGE_PORT", "QUINN_ENDPOINT", "QUINN_LOCAL_API_URL", "QUINN_BRIDGE_SECRET", "QUINN_LOCAL_TIMEOUT_MS", "QUINN_TIMEOUT_MS"]),
    ("Quinn Infrastructure (read-only)", ["QDRANT_HOST", "QDRANT_PORT", "QDRANT_TIMEOUT", "QDRANT_COLLECTION", "QDRANT_EMBEDDING_MODEL", "OLLAMA_HOST", "OLLAMA_PORT", "OLLAMA_MODEL"]),
    ("Model Selection", ["QUINN_LOCAL_MODEL", "QUINN_COMPRESS_MODEL", "SHIPSTACK_MODEL", "MODEL_OPENAI", "MODEL_ANTHROPIC"]),
    ("Fallback (Directive #3 enforced)", ["FALLBACK_ENABLED", "FALLBACK_PROVIDER", "FALLBACK_TIMEOUT_MS", "FALLBACK_MODEL"]),
    ("App Profile Routing", ["APP_PRIMARY_PROFILE", "APP_SECONDARY_PROFILE", "NODE_ENV"]),
    ("Paths (Windows)", ["SHIPSTACK_DIR", "LOG_DIR", "PYTHON_EXE", "FFMPEG_PATH", "TOOL_LOG_PATH"]),
    ("Business Profile", ["BUSINESS_NICHE", "BUSINESS_NAME", "WEBSITE_URL", "LANDING_PAGE_URL", "TARGET_PRODUCTS", "DEFAULT_PRODUCT_IMAGE_URL"]),
    ("Stripe", ["STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_SUCCESS_URL", "STRIPE_CANCEL_URL"]),
    ("Pinterest", ["PINTEREST_ACCESS_TOKEN", "PINTEREST_APP_ID", "PINTEREST_APP_SECRET", "PINTEREST_DEFAULT_BOARD_ID", "PINTEREST_BOARD_ID"]),
    ("Meta", ["META_ACCESS_TOKEN", "META_APP_ID", "META_APP_SECRET", "META_IG_ACCOUNT_ID", "META_PAGE_ID"]),
    ("TikTok", ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN"]),
    ("YouTube", ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]),
    ("Suppliers", ["ZENDROP_API_KEY", "AUTODS_API_KEY", "ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET"]),
    ("GitHub", ["GITHUB_TOKEN", "GITHUB_USERNAME", "GITHUB_PAGES_REPO"]),
    ("Media Generation", ["RUNWAY_API_KEY", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY"]),
    ("ngrok", ["NGROK_AUTHTOKEN"]),
    ("Vercel", ["VERCEL_TOKEN", "VERCEL_PROJECT_ID", "VERCEL_TEAM_ID", "VERCEL_SITE_URL"]),
])

SAFE_PREFIXES = ("http", "sk_", "pk_", "key_", "pina_", "ghp_", "vcp_", "sk-", "GOCSPX", "1//")

def parse_env(path):
    out = OrderedDict()
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  ERR reading {path}: {e}")
        return out
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k, v = k.strip(), v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        if "#" in v and not v.startswith(SAFE_PREFIXES):
            v = v.split("#")[0].strip()
        out[k] = v
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("=" * 70)
    print(f"  ShipStack .env consolidator | dry-run={args.dry_run}")
    print(f"  Target: {TARGET_ENV}")
    print("=" * 70)

    merged = OrderedDict()
    src_log = {}
    for src in SOURCES:
        if not src.exists():
            print(f"  skip (not found): {src}")
            continue
        env = parse_env(src)
        print(f"  read {src}: {len(env)} keys")
        for k, v in env.items():
            if v or not merged.get(k):
                if k in merged and merged[k] != v:
                    print(f"    OVERRIDE: {k}  (was from {src_log.get(k,'?')})")
                merged[k] = v
                src_log[k] = src.name

    dropped = []
    for k in list(FORBIDDEN_KEYS):
        if k in merged:
            dropped.append(k); del merged[k]
    for k, pat in FORBIDDEN_VAL.items():
        if k in merged and pat.search(merged[k] or ""):
            dropped.append(f"{k} (anthropic.com)"); del merged[k]
    for k, v in FORCED.items():
        if merged.get(k) != v:
            print(f"    FORCED: {k} = {v}")
        merged[k] = v

    print(f"\n  Total unique keys: {len(merged)}")
    if dropped:
        print(f"  Dropped per Directive #3: {dropped}")

    used = set()
    lines = [
        "# " + "=" * 68,
        "# SHIPSTACK AI - Consolidated .env (auto-generated)",
        f"# Generated: {datetime.now().isoformat(timespec='seconds')}",
        "# Directive #3: NO ANTHROPIC_API_KEY here. Quinn Gateway only.",
        "# DO NOT COMMIT - this file is gitignored. Commit .env.example only.",
        "# " + "=" * 68, "",
    ]
    for sec, keys in SECTIONS.items():
        lines.append(f"# ---- {sec} ----")
        for k in keys:
            if k in merged:
                lines.append(f"{k}={merged[k]}"); used.add(k)
            else:
                lines.append(f"{k}=")
        lines.append("")

    orphans = [k for k in merged if k not in used]
    if orphans:
        lines.append("# ---- Uncategorized ----")
        for k in orphans:
            lines.append(f"{k}={merged[k]}")
        lines.append("")

    output = "\n".join(lines)
    example_lines = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k, _, _ = line.partition("=")
            example_lines.append(f"{k.strip()}=")
        else:
            example_lines.append(line)
    example_output = "\n".join(example_lines)

    if args.dry_run:
        print("\n  [DRY RUN] No writes. Key names (no values):")
        for k in merged:
            print(f"    {k}")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if TARGET_ENV.exists():
        b = TARGET_ENV.parent / f".env.bak.{stamp}"
        shutil.copy2(TARGET_ENV, b); print(f"  backed up: {b.name}")
    if TARGET_EX.exists():
        b = TARGET_EX.parent / f".env.example.bak.{stamp}"
        shutil.copy2(TARGET_EX, b); print(f"  backed up: {b.name}")

    with open(TARGET_ENV, "w", encoding="utf-8", newline="\n") as f:
        f.write(output)
    print(f"  WROTE: {TARGET_ENV} ({len(output)} bytes)")
    with open(TARGET_EX, "w", encoding="utf-8", newline="\n") as f:
        f.write(example_output)
    print(f"  WROTE: {TARGET_EX} ({len(example_output)} bytes)")

    gi = ROOT / ".gitignore"
    if gi.exists():
        if ".env" in gi.read_text(encoding="utf-8", errors="replace"):
            print("  OK: .gitignore covers .env")
        else:
            print("  WARN: .gitignore does NOT contain '.env' - add it before commit!")
    else:
        print("  WARN: no .gitignore in dropship-os/")

    print("\n  Done. Inspect new .env, commit .env.example only.")

if __name__ == "__main__":
    main()
