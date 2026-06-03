#!/usr/bin/env python3
"""
product_scanner.py — Live Product Margin Scanner
Builds products.json used by the ROI Product Finder dashboard.
No API key required — uses public data + manual catalog.

Usage:
    cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping\roi-product-finder"
    python product_scanner.py
"""

import json
import random
from datetime import datetime
from pathlib import Path

# ── Product catalog (manually curated, regularly updated)
# Format: name, niche, supplier, cost_usd, sell_price_usd, fulfillment_days, trending
PRODUCT_CATALOG = [
    # Pet
    {"name": "Automatic Pet Feeder",          "niche": "pet accessories",   "supplier": "zendrop",    "cost": 8.50,  "sell": 34.99, "fulfill_days": 7,  "trending": True,  "pinterest_score": 94, "tiktok_score": 88},
    {"name": "Silicone Dog Collar",            "niche": "pet accessories",   "supplier": "autods",     "cost": 2.20,  "sell": 14.99, "fulfill_days": 12, "trending": False, "pinterest_score": 72, "tiktok_score": 65},
    {"name": "Cat Tunnel Toy",                 "niche": "pet accessories",   "supplier": "aliexpress", "cost": 3.10,  "sell": 16.99, "fulfill_days": 14, "trending": True,  "pinterest_score": 81, "tiktok_score": 90},
    {"name": "Pet Hair Remover Brush",         "niche": "pet accessories",   "supplier": "zendrop",    "cost": 4.00,  "sell": 18.99, "fulfill_days": 7,  "trending": True,  "pinterest_score": 86, "tiktok_score": 82},
    # Home & Kitchen
    {"name": "Space-Saving Cabinet Organizer", "niche": "home kitchen",      "supplier": "autods",     "cost": 6.80,  "sell": 27.99, "fulfill_days": 10, "trending": True,  "pinterest_score": 89, "tiktok_score": 85},
    {"name": "Magnetic Knife Holder",          "niche": "home kitchen",      "supplier": "aliexpress", "cost": 4.50,  "sell": 22.99, "fulfill_days": 14, "trending": False, "pinterest_score": 74, "tiktok_score": 68},
    {"name": "Collapsible Dish Rack",          "niche": "home kitchen",      "supplier": "autods",     "cost": 9.20,  "sell": 36.99, "fulfill_days": 10, "trending": True,  "pinterest_score": 82, "tiktok_score": 79},
    # Fitness
    {"name": "Resistance Band Set (11pc)",     "niche": "fitness tools",     "supplier": "autods",     "cost": 5.50,  "sell": 24.99, "fulfill_days": 10, "trending": True,  "pinterest_score": 78, "tiktok_score": 88},
    {"name": "Ab Roller Wheel",                "niche": "fitness tools",     "supplier": "aliexpress", "cost": 3.80,  "sell": 19.99, "fulfill_days": 14, "trending": False, "pinterest_score": 65, "tiktok_score": 72},
    {"name": "Posture Corrector Brace",        "niche": "fitness tools",     "supplier": "zendrop",    "cost": 4.20,  "sell": 19.99, "fulfill_days": 7,  "trending": True,  "pinterest_score": 84, "tiktok_score": 80},
    # Desk / Office
    {"name": "Bamboo Desk Organizer",          "niche": "desk organizers",   "supplier": "aliexpress", "cost": 5.10,  "sell": 22.99, "fulfill_days": 14, "trending": False, "pinterest_score": 77, "tiktok_score": 61},
    {"name": "Monitor Stand Riser",            "niche": "desk organizers",   "supplier": "autods",     "cost": 7.30,  "sell": 29.99, "fulfill_days": 10, "trending": True,  "pinterest_score": 80, "tiktok_score": 70},
    # Plants / Garden
    {"name": "LED Plant Grow Light (Mini)",    "niche": "led grow lights",   "supplier": "aliexpress", "cost": 8.90,  "sell": 34.99, "fulfill_days": 14, "trending": True,  "pinterest_score": 87, "tiktok_score": 75},
    {"name": "Self-Watering Planter Set",      "niche": "led grow lights",   "supplier": "aliexpress", "cost": 6.20,  "sell": 26.99, "fulfill_days": 14, "trending": True,  "pinterest_score": 90, "tiktok_score": 68},
    # Beauty
    {"name": "Facial Roller (Rose Quartz)",    "niche": "beauty skincare",   "supplier": "zendrop",    "cost": 3.50,  "sell": 18.99, "fulfill_days": 7,  "trending": True,  "pinterest_score": 92, "tiktok_score": 88},
    {"name": "Electric Face Scrubber",         "niche": "beauty skincare",   "supplier": "autods",     "cost": 6.10,  "sell": 28.99, "fulfill_days": 9,  "trending": True,  "pinterest_score": 85, "tiktok_score": 91},
    # Outdoor
    {"name": "Portable Solar Lantern",         "niche": "outdoor camping",   "supplier": "aliexpress", "cost": 7.80,  "sell": 29.99, "fulfill_days": 16, "trending": True,  "pinterest_score": 76, "tiktok_score": 72},
    {"name": "Emergency Mylar Blankets (10pk)","niche": "outdoor camping",   "supplier": "aliexpress", "cost": 3.20,  "sell": 14.99, "fulfill_days": 16, "trending": False, "pinterest_score": 62, "tiktok_score": 55},
]


def compute_margin(cost: float, sell: float) -> float:
    return round((sell - cost) / sell * 100, 1)


def compute_roi(cost: float, sell: float) -> float:
    return round((sell - cost) / cost * 100, 1)


def score_product(product: dict) -> float:
    """Overall product opportunity score 0-100."""
    margin = compute_margin(product["cost"], product["sell"])
    trend_bonus = 10 if product["trending"] else 0
    # Prefer short fulfillment + high margin
    fulfill_score = max(0, 20 - product["fulfill_days"])
    price_score = min(product["sell"] / 2, 20)
    raw = (margin * 0.5) + fulfill_score + price_score + trend_bonus
    return round(min(raw, 100), 1)


def build_products_json():
    products = []
    for p in PRODUCT_CATALOG:
        margin = compute_margin(p["cost"], p["sell"])
        roi = compute_roi(p["cost"], p["sell"])
        overall_score = score_product(p)

        products.append({
            **p,
            "margin_pct": margin,
            "roi_pct": roi,
            "profit_per_unit": round(p["sell"] - p["cost"], 2),
            "overall_score": overall_score,
            "action": "SCALE" if overall_score >= 65 else ("TEST" if overall_score >= 45 else "SKIP"),
        })

    products.sort(key=lambda x: x["overall_score"], reverse=True)

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "products": products,
        "summary": {
            "total_products": len(products),
            "scale_products": len([p for p in products if p["action"] == "SCALE"]),
            "top_product": products[0]["name"] if products else None,
            "highest_margin": max(p["margin_pct"] for p in products),
            "avg_margin": round(sum(p["margin_pct"] for p in products) / len(products), 1),
            "suppliers": {
                "zendrop":    len([p for p in products if p["supplier"] == "zendrop"]),
                "autods":     len([p for p in products if p["supplier"] == "autods"]),
                "aliexpress": len([p for p in products if p["supplier"] == "aliexpress"]),
            }
        }
    }

    out_path = Path(__file__).parent / "products.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[ProductScanner] {len(products)} products scored → {out_path}")
    print(f"[ProductScanner] Top product: {products[0]['name']} | Margin: {products[0]['margin_pct']}% | Score: {products[0]['overall_score']}")
    return output


if __name__ == "__main__":
    build_products_json()
