#!/usr/bin/env python3
"""
run_dropship_os.py — ShipStack AI Master Orchestrator
One command to run the entire system.

Usage:
    cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping"

    python run_dropship_os.py --status          # check all connections
    python run_dropship_os.py --research        # run trend research → update decisions
    python run_dropship_os.py --generate        # generate content for top 3 combos
    python run_dropship_os.py --schedule        # build posting queue
    python run_dropship_os.py --post --dry-run  # preview what would be posted
    python run_dropship_os.py --post            # post everything due now
    python run_dropship_os.py --spin-pages      # generate landing pages for top combos
    python run_dropship_os.py --monitor         # check Stripe + place supplier orders
    python run_dropship_os.py --full            # run EVERYTHING (daily full cycle)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60 + "\n")


def cmd_status():
    print_header("SHIPSTACK AI — SYSTEM STATUS")

    # Social poster
    try:
        from integrations.social_poster import SocialPoster
        poster = SocialPoster()
        print("📡 Social Platforms:")
        for platform, status in poster.status().items():
            print(f"   {platform:<20} {status}")
    except Exception as e:
        print(f"   Social poster error: {e}")

    # Suppliers
    try:
        from integrations.supplier_connector import ZendropConnector, AutoDSConnector
        z, a = ZendropConnector(), AutoDSConnector()
        print("\n📦 Suppliers:")
        print(f"   Zendrop   {'✅ Ready' if z.is_configured() else '❌ Add ZENDROP_API_KEY to .env'}")
        print(f"   AutoDS    {'✅ Ready' if a.is_configured() else '❌ Add AUTODS_API_KEY to .env'}")
    except Exception as e:
        print(f"   Supplier error: {e}")

    # Stripe
    import os
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    print(f"\n💳 Stripe:      {'✅ Ready' if stripe_key else '❌ Add STRIPE_SECRET_KEY to .env'}")

    # Data files
    print("\n📊 Data Files:")
    files = [
        ("decisions.json",                      "Decision Engine output"),
        ("roi-product-finder/products.json",    "Product catalog"),
        ("social_ai_agent/data/trend_results.json", "Trend research"),
        ("content_pipeline/content_batch.json", "Generated content"),
        ("content_pipeline/post_queue.json",    "Post queue"),
        ("data/stripe_links.json",              "Stripe payment links"),
        ("data/order_log.json",                 "Order log"),
    ]
    for fname, label in files:
        exists = (BASE_DIR / fname).exists()
        print(f"   {'✅' if exists else '❌'} {label:<35} {fname}")

    print("\n💡 Run 'python run_shipstack.py --full' for a complete daily cycle.\n")


def cmd_research():
    print_header("STEP 1 — TREND RESEARCH")
    import subprocess
    result = subprocess.run(
        [sys.executable, "social_ai_agent/run_trend_research.py"],
        cwd=str(BASE_DIR)
    )
    if result.returncode == 0:
        print("\n✅ Research complete. Running Decision Engine...")
        cmd_decision()


def cmd_decision():
    print_header("STEP 2 — DECISION ENGINE")
    import subprocess
    subprocess.run([sys.executable, "decision_engine.py"], cwd=str(BASE_DIR))


def cmd_generate():
    print_header("STEP 3 — CONTENT GENERATION")
    import subprocess
    subprocess.run(
        [sys.executable, "content_pipeline/generate_content.py"],
        cwd=str(BASE_DIR)
    )


def cmd_prometheus(max_products: int = 3):
    """Run Prometheus Engine for top decision engine products."""
    print_header("PROMETHEUS CREATION STUDIO")
    import subprocess

    decisions_path = BASE_DIR / "decisions.json"
    if not decisions_path.exists():
        print("No decisions.json — run --research first")
        return

    data = json.loads(decisions_path.read_text())
    top = data.get("top_combos", [])[:max_products]

    print(f"Generating content for {len(top)} top combos...")
    for i, combo in enumerate(top, 1):
        product = combo.get("product", "Product")
        niche   = combo.get("niche", "general")
        print(f"\n[{i}/{len(top)}] {product} ({niche})")
        subprocess.run(
            [sys.executable, "prometheus_engine.py",
             "--product", product, "--niche", niche],
            cwd=str(BASE_DIR)
        )


def cmd_pinterest(max_posts: int = 3, dry_run: bool = False):
    """Auto-post top products to Pinterest."""
    print_header("PINTEREST AUTO-POST")
    import subprocess

    cmd = [sys.executable, "social_ai_agent/pinterest_poster.py", "--auto", "--max", str(max_posts)]
    if dry_run:
        print("[DRY RUN] Would run:", " ".join(cmd))
        return
    subprocess.run(cmd, cwd=str(BASE_DIR))


def cmd_schedule():
    print_header("STEP 4 — BUILD POST QUEUE")
    import subprocess
    subprocess.run(
        [sys.executable, "content_pipeline/post_scheduler.py"],
        cwd=str(BASE_DIR)
    )


def cmd_post(dry_run: bool = False):
    print_header("STEP 5 — POST CONTENT")
    from integrations.social_poster import SocialPoster
    poster = SocialPoster()
    results = poster.run_queue(dry_run=dry_run)
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Posted {len(results)} pieces of content")


def cmd_spin_pages():
    print_header("STEP 6 — SPIN LANDING PAGES")

    decisions_path = BASE_DIR / "decisions.json"
    if not decisions_path.exists():
        print("No decisions.json. Run --research first.")
        return

    data = json.loads(decisions_path.read_text())
    top_combos = data.get("top_combos", [])[:3]

    # Create Stripe links + pages for each top combo
    try:
        from integrations.stripe_checkout import StripeCheckout
        sc = StripeCheckout()
    except Exception:
        sc = None

    import subprocess
    for combo in top_combos:
        product = combo["product"]
        niche = combo["niche"]
        price = 29.99

        stripe_link = "#"
        if sc:
            result = sc.create_product_and_link(product, price)
            stripe_link = result.get("payment_link_url", "#")

        subprocess.run(
            [sys.executable, "asset_machine/spin_page.py",
             "--product", product, "--niche", niche,
             "--price", str(price), "--stripe", stripe_link],
            cwd=str(BASE_DIR)
        )

    print(f"\n✅ {len(top_combos)} landing pages generated → asset_machine/pages/")


def cmd_monitor():
    print_header("STEP 7 — ORDER MONITOR")
    from integrations.supplier_connector import OrderMonitor
    monitor = OrderMonitor()
    orders = monitor.poll()
    print(f"\n✅ Processed {len(orders)} new orders")
    if orders:
        for o in orders:
            print(f"   💳 {o['stripe_charge_id']} | ${o['amount_usd']:.2f} | {o['product']}")


def cmd_full(dry_run: bool = False):
    print_header("FULL DAILY CYCLE")
    print("Steps: Research → Decide → Prometheus → Pinterest → Generate → Schedule → Post → Pages → Monitor\n")
    cmd_research()
    cmd_prometheus(max_products=3)
    cmd_pinterest(max_posts=3, dry_run=dry_run)
    cmd_generate()
    cmd_schedule()
    cmd_post(dry_run=dry_run)
    cmd_spin_pages()
    cmd_monitor()
    print("\n🏁 Full cycle complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShipStack AI Master Orchestrator")
    parser.add_argument("--status",     action="store_true", help="Check all connections")
    parser.add_argument("--research",   action="store_true", help="Run trend research")
    parser.add_argument("--generate",   action="store_true", help="Generate content")
    parser.add_argument("--prometheus", action="store_true", help="Run Prometheus video pipeline for top products")
    parser.add_argument("--pinterest",  action="store_true", help="Auto-post to Pinterest")
    parser.add_argument("--schedule",   action="store_true", help="Build post queue")
    parser.add_argument("--post",       action="store_true", help="Post due content")
    parser.add_argument("--spin-pages", action="store_true", help="Generate landing pages")
    parser.add_argument("--monitor",    action="store_true", help="Check payments + fulfill orders")
    parser.add_argument("--full",       action="store_true", help="Run full daily cycle")
    parser.add_argument("--dry-run",    action="store_true", help="Preview without posting")
    parser.add_argument("--max",        type=int, default=3, help="Max products/posts (default: 3)")
    args = parser.parse_args()

    if args.status:     cmd_status()
    if args.research:   cmd_research()
    if args.generate:   cmd_generate()
    if args.prometheus: cmd_prometheus(max_products=args.max)
    if args.pinterest:  cmd_pinterest(max_posts=args.max, dry_run=args.dry_run)
    if args.schedule:   cmd_schedule()
    if args.post:       cmd_post(dry_run=args.dry_run)
    if args.spin_pages: cmd_spin_pages()
    if args.monitor:    cmd_monitor()
    if args.full:       cmd_full(dry_run=args.dry_run)

    if not any(vars(args).values()):
        parser.print_help()
