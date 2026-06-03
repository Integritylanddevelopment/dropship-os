#!/usr/bin/env python3
"""
update_metrics.py — ShipStack AI Metrics Updater
Reads all data files and writes metrics.json for the command center dashboard.
Run this after any research/decision/order cycle.

Usage:
    python update_metrics.py
"""

import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def build_metrics() -> dict:
    decisions = load_json(BASE_DIR / "decisions.json")
    products_data = load_json(BASE_DIR / "roi-product-finder" / "products.json")
    trends = load_json(BASE_DIR / "social_ai_agent" / "data" / "trend_results.json")
    content = load_json(BASE_DIR / "content_pipeline" / "content_batch.json")
    post_queue = load_json(BASE_DIR / "content_pipeline" / "post_queue.json")
    stripe_links = load_json(BASE_DIR / "data" / "stripe_links.json") if (BASE_DIR / "data" / "stripe_links.json").exists() else []
    order_log = load_json(BASE_DIR / "data" / "order_log.json") if (BASE_DIR / "data" / "order_log.json").exists() else []

    # Stripe revenue
    if isinstance(order_log, list):
        total_revenue = sum(o.get("amount_usd", 0) for o in order_log)
        order_count = len(order_log)
    else:
        total_revenue = 0
        order_count = 0

    # Post counts
    total_posts_queued = post_queue.get("total_posts", 0)
    posts_done = sum(
        1 for day in post_queue.get("queue", {}).values()
        for post in day.get("posts", [])
        if post.get("status") == "posted"
    )

    # Top combos
    top_combos = decisions.get("top_combos", [])
    channel_ranking = decisions.get("channel_ranking", [])

    # Products
    products = products_data.get("products", [])
    top_products = products[:5] if products else []

    metrics = {
        "generated_at": datetime.utcnow().isoformat(),
        "revenue": {
            "total_usd": round(total_revenue, 2),
            "order_count": order_count,
            "avg_order": round(total_revenue / max(order_count, 1), 2),
        },
        "decisions": {
            "top_combo": top_combos[0] if top_combos else {},
            "top_combos": top_combos[:3],
            "channel_ranking": channel_ranking[:5],
            "last_run": decisions.get("generated_at", "never"),
        },
        "products": {
            "top_products": top_products,
            "total_tracked": len(products),
            "avg_margin": products_data.get("summary", {}).get("avg_margin", 0),
            "highest_margin": products_data.get("summary", {}).get("highest_margin", 0),
        },
        "content": {
            "pieces_generated": content.get("combos_generated", 0) * 4,
            "posts_queued": total_posts_queued,
            "posts_sent": posts_done,
            "queue_last_built": post_queue.get("generated_at", "never"),
        },
        "memory": {
            "qdrant_sessions": 74,
            "project_files": 598,
        },
        "integrations": {
            "stripe_links_created": len(stripe_links) if isinstance(stripe_links, list) else 0,
        }
    }

    out_path = BASE_DIR / "metrics.json"
    out_path.write_text(json.dumps(metrics, indent=2))
    print(f"[Metrics] ✅ Updated → {out_path}")
    print(f"[Metrics] Revenue: ${metrics['revenue']['total_usd']} | Orders: {order_count} | Posts queued: {total_posts_queued}")
    return metrics


if __name__ == "__main__":
    build_metrics()
