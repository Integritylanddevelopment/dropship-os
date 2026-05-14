#!/usr/bin/env python3
"""
Qdrant Hard-Wall Partition Setup — Dropship OS

GOAL: Pull ONLY dropshipping content into dropship_intel, ONLY power/war strategy
into strategy_books. Everything else (Grand Prix social, enterprise agents,
other projects) is SKIPPED — never touches either collection.

THREE-BUCKET LOGIC:
  1. Does it match strategy signals?  → strategy_books
  2. Does it match dropship signals?  → dropship_intel
  3. Neither?                         → SKIP (stays in general_knowledge only)

FILTERS:
  --hours N     Only process chunks embedded in the last N hours (default: all)
                Use --hours 24 to only ingest today's new embeddings
  --dry-run     Preview counts only — no writes
  --report      Show sample chunks per bucket

Run:
  python SETUP_QDRANT_PARTITIONS.py --dry-run --report    # safe preview
  python SETUP_QDRANT_PARTITIONS.py --hours 24            # last 24h only
  python SETUP_QDRANT_PARTITIONS.py                       # full history, dropship+strategy only
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

_QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
_QDRANT_PORT = os.getenv("QDRANT_PORT", "6333")
QDRANT_URL = f"http://{_QDRANT_HOST}:{_QDRANT_PORT}"

SOURCE_COLLECTION   = "general_knowledge"
DROPSHIP_COLLECTION = "dropship_intel"
STRATEGY_COLLECTION = "strategy_books"

# ── STRATEGY SIGNALS (hard wall — any match → strategy_books) ─────────────────
# These are so specific they can't appear in dropshipping content accidentally.

STRATEGY_SIGNALS = [
    # 48 Laws of Power / Robert Greene
    "48 laws", "48laws", "law of power", "laws of power",
    "robert greene", "conceal your intentions",
    "never outshine the master", "always say less than necessary",
    "use absence to increase respect", "keep others in suspended terror",
    "discover each man's thumbscrew", "pose as a friend work as a spy",
    "crush your enemy totally", "use selective honesty",
    "do not commit to anyone", "create compelling spectacle",

    # Sun Tzu / Art of War
    "art of war", "sun tzu", "suntzu",
    "victorious warriors win first", "all warfare is based on deception",
    "appear weak when you are strong", "speed is the essence of war",
    "opportunities multiply as they are seized",
    "supreme art of war", "know yourself know your enemy",

    # Machiavelli / The Prince
    "machiavelli", "the prince", "il principe",
    "it is better to be feared than loved",
    "the ends justify", "principalities",
    "the lion and the fox",

    # Game Theory
    "game theory", "nash equilibrium", "nash's equilibrium",
    "prisoner's dilemma", "zero-sum game", "zero sum game",
    "dominant strategy", "payoff matrix", "minimax theorem",
    "pareto optimal", "tit for tat", "von neumann", "john nash",
    "schelling point", "cooperative game", "non-cooperative game",

    # Hard power/war strategy (tight phrases only — no single common words)
    "strategic deception", "power dynamics", "outmaneuver",
    "war of attrition", "flanking strategy", "divide and conquer",
    "leverage over opponents", "information asymmetry advantage",
    "conceal your", "position of power",
]

# ── DROPSHIP POSITIVE SIGNALS (must match to enter dropship_intel) ────────────
# Content must ACTIVELY prove it belongs here. Non-dropship content gets skipped.

DROPSHIP_SIGNALS = [
    # Core identity terms
    "drop ship", "dropship", "drop-ship", "drop shipping",
    "dropshipping", "ecom king", "ecommerce store", "online store",

    # Key people (tight — not just "gary" or "alex")
    "gary vee", "gary v", "gary vaynerchuk", "vaynerchuk",
    "alex hormozi", "hormozi", "$100m offers", "100m offers",
    "kamil sattar", "ecom king", "kamil sattar",

    # Platforms & tools
    "shopify", "zendrop", "autods", "aliexpress", "ali express",
    "cj dropshipping", "cjdropshipping",
    "woocommerce", "bigcommerce",

    # Metrics (tight phrases — avoids grabbing anything mentioning "margin")
    "roas", "return on ad spend", "cost per click", "cost per mille",
    " cpm ", " cpc ", " ctr ", "ad spend",
    "profit margin product", "product margin",

    # Channels in dropshipping context
    "pinterest organic", "pinterest strategy", "pinterest traffic",
    "tiktok organic", "tiktok shop", "instagram reels product",
    "youtube shorts product", "cheapest attention",
    "attention arbitrage",

    # Suppliers & fulfillment
    "supplier", "fulfillment center", "fulfill orders",
    "print on demand", "private label",
    "winning product", "trending product", "product research",
    "niche product", "dropship product",

    # Content strategy (dropship-specific)
    "viral product", "ugc content", "product video",
    "content repurpos", "pillar content strategy",
    "hook formula", "scroll stop",

    # Offers (Hormozi-specific compound terms)
    "grand slam offer", "value stack", "irresistible offer",
    "risk reversal", "money back guarantee", "lead magnet funnel",

    # Tech / payment (dropship context)
    "stripe payment link", "stripe checkout",
    "github pages store", "landing page product",
    "order monitor", "auto fulfill",

    # This project's own terms
    "dropship os", "decision engine", "roi intelligence",
    "channel arbitrage", "social ai agent dropship",
    "dropship intel", "attention tracker",
]

# ── SKIP SIGNALS — content with these is NOT dropship or strategy ─────────────
# These flag content from other projects that should never enter either collection.

SKIP_SIGNALS = [
    "grand prix", "grandprix", "formula 1", "formula one", "f1 race",
    "jessica", "aftercare", "gp consultant", "gp investigation",
    "healthcare", "medical", "patient", "clinic",
    "togetherwe site", "together we site",
    "commandcore", "command core", "enterprise agent",
    "tier 1 agent", "tier1 agent", "master orchestrator",
]


# ── CLASSIFIER ────────────────────────────────────────────────────────────────

def classify(text: str, metadata: dict, min_score: int = 1) -> str:
    """
    Returns 'strategy_books', 'dropship_intel', or 'SKIP'.

    Hard rules (in order):
    1. Any skip signal present → SKIP (other project content)
    2. Any strategy signal present → strategy_books
    3. At least min_score dropship signals → dropship_intel
    4. Otherwise → SKIP
    """
    combined = (text + " " + json.dumps(metadata)).lower()

    # Rule 1: other-project content — skip immediately
    for sig in SKIP_SIGNALS:
        if sig in combined:
            return "SKIP"

    # Rule 2: strategy — hard wall, one signal is enough
    for sig in STRATEGY_SIGNALS:
        if sig in combined:
            return "strategy_books"

    # Rule 3: dropship — must match at least min_score signals
    score = sum(1 for sig in DROPSHIP_SIGNALS if sig in combined)
    if score >= min_score:
        return "dropship_intel"

    # Rule 4: no clear match — skip (don't contaminate either collection)
    return "SKIP"


def parse_timestamp(ts_str: str):
    """Parse ISO timestamp string to datetime. Returns None on failure."""
    if not ts_str:
        return None
    try:
        ts = ts_str.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        try:
            return datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None


# ── QDRANT HELPERS ────────────────────────────────────────────────────────────

def collection_exists(name: str) -> bool:
    r = httpx.get(f"{QDRANT_URL}/collections/{name}", timeout=5)
    return r.status_code == 200


def get_vector_size(collection: str) -> int:
    r = httpx.get(f"{QDRANT_URL}/collections/{collection}", timeout=5)
    if r.status_code == 200:
        cfg = r.json().get("result", {}).get("config", {}).get("params", {})
        v = cfg.get("vectors", {})
        if isinstance(v, dict) and "size" in v:
            return v["size"]
    return 384


def create_collection(name: str, vector_size: int = 384):
    if collection_exists(name):
        print(f"    · '{name}' already exists")
        return
    r = httpx.put(
        f"{QDRANT_URL}/collections/{name}",
        json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        timeout=10,
    )
    print(f"    {'✓' if r.status_code == 200 else '✗'} Created '{name}'")
    if r.status_code != 200:
        sys.exit(1)


def scroll_all(collection: str) -> list:
    all_pts, offset = [], None
    print(f"  Scrolling '{collection}'...", end="", flush=True)
    while True:
        body = {"limit": 100, "with_payload": True, "with_vector": True}
        if offset:
            body["offset"] = offset
        r = httpx.post(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            json=body, timeout=30,
        )
        if r.status_code != 200:
            print(f"\n  ✗ {r.text}")
            break
        data = r.json().get("result", {})
        pts = data.get("points", [])
        all_pts.extend(pts)
        print(f" {len(all_pts)}", end="", flush=True)
        if not data.get("next_page_offset"):
            break
        offset = data["next_page_offset"]
    print()
    return all_pts


def upsert_batch(collection: str, points: list) -> bool:
    payload = [
        {"id": p["id"], "vector": p.get("vector", []), "payload": p.get("payload", {})}
        for p in points
    ]
    r = httpx.put(
        f"{QDRANT_URL}/collections/{collection}/points",
        json={"points": payload},
        timeout=30,
    )
    return r.status_code == 200


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    global QDRANT_URL

    ap = argparse.ArgumentParser(description="Qdrant hard-wall partition setup")
    ap.add_argument("--hours", type=float, default=None,
                    help="Only process chunks from the last N hours (e.g. --hours 24)")
    ap.add_argument("--dry-run", action="store_true", help="Preview only — no writes")
    ap.add_argument("--report", action="store_true", help="Show 3 sample chunks per bucket")
    ap.add_argument("--qdrant", default=QDRANT_URL)
    ap.add_argument("--min-signals", type=int, default=1,
                    help="Minimum dropship signals required (default 1, raise to tighten)")
    args = ap.parse_args()

    QDRANT_URL = args.qdrant

    cutoff = None
    if args.hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    print()
    print("=" * 66)
    print("  Qdrant Hard-Wall Partition — Dropship OS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 66)
    print(f"  Source:         {SOURCE_COLLECTION}")
    print(f"  dropship_intel: Gary V / Hormozi / Kamil / products / channels")
    print(f"  strategy_books: 48 Laws / Art of War / Machiavelli / Game Theory")
    print(f"  SKIP:           Grand Prix / enterprise agents / other projects")
    print(f"  Time filter:    {'last %.0fh' % args.hours if args.hours else 'all time'}")
    print(f"  Min signals:    {args.min_signals}")
    print(f"  Dry run:        {args.dry_run}")
    print()

    # Verify source
    if not collection_exists(SOURCE_COLLECTION):
        print(f"  ✗ '{SOURCE_COLLECTION}' not found. Is Qdrant running at {QDRANT_URL}?")
        sys.exit(1)

    vec_size = get_vector_size(SOURCE_COLLECTION)
    print(f"  Vector dims: {vec_size}")

    # Create partitions
    if not args.dry_run:
        print("\n  Creating partitions...")
        create_collection(DROPSHIP_COLLECTION, vec_size)
        create_collection(STRATEGY_COLLECTION, vec_size)

    # Load all points
    print()
    all_points = scroll_all(SOURCE_COLLECTION)
    print(f"  Total in source: {len(all_points)}")

    # Apply time filter
    if cutoff:
        before = len(all_points)
        filtered = []
        for p in all_points:
            ts_str = p.get("payload", {}).get("timestamp", "")
            ts = parse_timestamp(ts_str)
            if ts and ts >= cutoff:
                filtered.append(p)
            elif not ts_str:
                # No timestamp — include it (can't exclude what we can't date)
                filtered.append(p)
        all_points = filtered
        print(f"  After time filter (last {args.hours:.0f}h): {len(all_points)} / {before}")

    if not all_points:
        print("\n  Nothing to process.")
        return

    # Classify
    dropship_pts, strategy_pts, skip_pts = [], [], []
    skip_reasons = {}

    for p in all_points:
        text = p.get("payload", {}).get("text", "") or ""
        meta = {k: v for k, v in p.get("payload", {}).items() if k != "text"}
        dest = classify(text, meta, min_score=args.min_signals)

        if dest == "dropship_intel":
            dropship_pts.append(p)
        elif dest == "strategy_books":
            strategy_pts.append(p)
        else:
            skip_pts.append(p)
            # Track why it was skipped
            combined = (text + " " + json.dumps(meta)).lower()
            for sig in SKIP_SIGNALS:
                if sig in combined:
                    skip_reasons[sig] = skip_reasons.get(sig, 0) + 1
                    break

    total_processed = len(dropship_pts) + len(strategy_pts)
    total_skipped = len(skip_pts)

    print()
    print("  ── Classification Results ──────────────────────────────────")
    print(f"  dropship_intel  : {len(dropship_pts):>6} chunks  ← goes in")
    print(f"  strategy_books  : {len(strategy_pts):>6} chunks  ← goes in")
    print(f"  SKIPPED         : {total_skipped:>6} chunks  ← other projects (not written)")
    print(f"  Total processed : {total_processed:>6} chunks")
    print()

    if skip_reasons:
        print("  Top skip signals (other-project content blocked):")
        for sig, cnt in sorted(skip_reasons.items(), key=lambda x: -x[1])[:8]:
            print(f"    '{sig}': {cnt} chunks blocked")
        print()

    # Report
    if args.report:
        print("  ── Sample: strategy_books ──────────────────────────────────")
        for p in strategy_pts[:3]:
            print(f"    {p.get('payload', {}).get('text', '')[:180]!r}")
            print()
        print("  ── Sample: dropship_intel ──────────────────────────────────")
        for p in dropship_pts[:3]:
            print(f"    {p.get('payload', {}).get('text', '')[:180]!r}")
            print()
        print("  ── Sample: SKIPPED ─────────────────────────────────────────")
        for p in skip_pts[:3]:
            print(f"    {p.get('payload', {}).get('text', '')[:180]!r}")
            print()

    if args.dry_run:
        print("  [DRY RUN] Nothing written. Remove --dry-run to apply.")
        return

    # Write dropship_intel
    print("  Writing dropship_intel...")
    ok = 0
    for i in range(0, len(dropship_pts), 50):
        batch = dropship_pts[i:i+50]
        success = upsert_batch(DROPSHIP_COLLECTION, batch)
        ok += len(batch) if success else 0
        print(f"    batch {i//50+1}: {'✓' if success else '✗'} ({len(batch)} pts)")
    print(f"  → {ok}/{len(dropship_pts)} written\n")

    # Write strategy_books
    print("  Writing strategy_books...")
    ok = 0
    for i in range(0, len(strategy_pts), 50):
        batch = strategy_pts[i:i+50]
        success = upsert_batch(STRATEGY_COLLECTION, batch)
        ok += len(batch) if success else 0
        print(f"    batch {i//50+1}: {'✓' if success else '✗'} ({len(batch)} pts)")
    print(f"  → {ok}/{len(strategy_pts)} written\n")

    print("  ── Complete ────────────────────────────────────────────────")
    print(f"  ✓ dropship_intel : {len(dropship_pts)} chunks (Gary V / Hormozi / products)")
    print(f"  ✓ strategy_books : {len(strategy_pts)} chunks (48 Laws / Art of War / Machiavelli)")
    print(f"  ✗ skipped        : {total_skipped} chunks (Grand Prix / other — not contaminating)")
    print(f"  ✓ general_knowledge untouched (source of truth)")
    print()
    if args.hours:
        print(f"  Run again without --hours to process full history.")
        print(f"  Run with --hours 24 daily to ingest new embeddings only.")
    print()


if __name__ == "__main__":
    main()
