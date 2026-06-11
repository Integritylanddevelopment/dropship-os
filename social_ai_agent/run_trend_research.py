#!/usr/bin/env python3
"""
run_trend_research.py — Dropship Trend Research Runner
Run this daily (or on demand) to update the Decision Engine.

Usage:
    cd "C:\Users\integ\Documents\Claude\Projects\ShipStack\social_ai_agent"
    python run_trend_research.py

    # Custom niches:
    python run_trend_research.py --niches "pet accessories,home kitchen,fitness tools"

    # Skip Qdrant indexing (JSON output only):
    python run_trend_research.py --no-qdrant
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Make sure imports work from this directory
sys.path.insert(0, str(Path(__file__).parent))

from research.trend_engine import TrendEngine, NICHE_PROFILES
from research.qdrant_indexer import QdrantIndexer


DEFAULT_NICHES = [
    "pet accessories",
    "home kitchen",
    "fitness tools",
    "desk organizers",
    "posture corrector",
    "led grow lights",
    "beauty skincare",
    "outdoor camping",
]


def main():
    parser = argparse.ArgumentParser(description="Dropship Trend Research Runner")
    parser.add_argument("--niches", type=str, default=None, help="Comma-separated niches to analyze")
    parser.add_argument("--timeframe", type=str, default="today 3-m", help="Google Trends timeframe (default: today 3-m)")
    parser.add_argument("--no-qdrant", action="store_true", help="Skip Qdrant indexing")
    args = parser.parse_args()

    print("=" * 60)
    print("  DROPSHIP TREND RESEARCH ENGINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    niches = [n.strip() for n in args.niches.split(",")] if args.niches else DEFAULT_NICHES
    print(f"\n📊 Analyzing {len(niches)} niches: {', '.join(niches)}\n")

    # 1. Fetch trends + score combos
    engine = TrendEngine()
    results = engine.run(niches=niches, timeframe=args.timeframe)

    # 2. Index into Qdrant
    if not args.no_qdrant:
        print("\n🧠 Indexing into Qdrant memory stack...")
        indexer = QdrantIndexer()
        indexed = indexer.index_trend_results(results)
        print(f"   → {indexed} records indexed")

    # 3. Print decision summary
    print("\n" + "=" * 60)
    print("  DECISION ENGINE OUTPUT")
    print("=" * 60)

    scale = results["decision"].get("scale", [])
    test  = results["decision"].get("test", [])
    kill  = results["decision"].get("kill", [])

    print(f"\n🟢 SCALE NOW ({len(scale)} combos):")
    for c in scale[:3]:
        print(f"   #{scale.index(c)+1}  {c['niche'].upper()} × {c['channel']}  |  Score {c['score']}  |  Margin {c['margin_pct']}%  |  CPM ${c['cpm']}")

    print(f"\n🟡 TEST ({len(test)} combos):")
    for c in test[:3]:
        print(f"   -  {c['niche']} × {c['channel']}  |  Score {c['score']}")

    print(f"\n🔴 KILL ({len(kill)} combos):")
    for c in kill[:3]:
        print(f"   ✗  {c['niche']} × {c['channel']}  |  Score {c['score']}")

    print(f"\n📡 CHEAPEST CHANNELS (Gary Vee ranking):")
    for i, ch in enumerate(results["channel_rankings"][:5], 1):
        cpm_str = "FREE" if ch["cpm"] == 0 else f"${ch['cpm']}"
        print(f"   {i}. {ch['channel']}  |  CPM {cpm_str}  |  Efficiency {ch['efficiency_score']}")

    data_path = Path(__file__).parent / "data" / "trend_results.json"
    print(f"\n✅ Full results saved → {data_path}")
    print("\nNext: Run decision_engine.py to push top combos to the command center.\n")


if __name__ == "__main__":
    main()
