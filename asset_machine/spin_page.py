#!/usr/bin/env python3
"""
asset_machine/spin_page.py — Auto-Spin Landing Pages
Reads decisions.json, grabs top combo, generates a one-page
sales site ready for GitHub Pages + Stripe checkout.

Usage:
    cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping"
    python asset_machine/spin_page.py

    # Custom product:
    python asset_machine/spin_page.py --product "Automatic Pet Feeder" --price 34.99 --niche "pet accessories"

    # Deploy to GitHub Pages after generating:
    # 1. Copy output file to your GitHub Pages repo
    # 2. git add . && git commit -m "new page" && git push
"""

import json
import argparse
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = Path(__file__).parent / "pages"

EMOJI_MAP = {
    "pet accessories":  "🐾", "home kitchen":   "🏠", "fitness tools":  "💪",
    "beauty skincare":  "✨", "desk organizers":"📚", "led grow lights":"🌿",
    "outdoor camping":  "🏕️", "general":        "⭐",
}


def load_top_combo() -> dict:
    decisions_path = BASE_DIR / "decisions.json"
    if decisions_path.exists():
        data = json.loads(decisions_path.read_text())
        top = data.get("top_combos", [])
        if top:
            return top[0]
    return {}


def build_page(product_name: str, price: float, niche: str, channel: str,
               stripe_link: str = "#") -> tuple:

    slug = re.sub(r"[^a-z0-9]+", "-", product_name.lower()).strip("-")
    emoji = EMOJI_MAP.get(niche, "⭐")
    year = datetime.now().year

    # Hormozi offer bullets
    bullets = [
        f"Solves your biggest {niche} headache — instantly",
        "Ships in 7 days or less, direct to your door",
        "30-day money-back guarantee — zero risk, zero questions",
        "Join 10,000+ satisfied customers",
        "Limited stock — once it's gone it's gone",
    ]
    bullets_html = "\n".join([f'<li>{b}</li>' for b in bullets])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{product_name} — Get Yours Today</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0a0f1a;color:#e4eaf0;line-height:1.6}}
  .hero{{background:linear-gradient(135deg,#0d1a2e 0%,#1a3050 100%);padding:80px 20px;text-align:center}}
  .emoji{{font-size:72px;margin-bottom:20px;display:block}}
  .hero h1{{font-size:clamp(28px,5vw,52px);font-weight:900;line-height:1.1;margin-bottom:16px;
             background:linear-gradient(135deg,#38bdf8,#22d3a0);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
  .hero p{{font-size:18px;color:#94aabb;max-width:560px;margin:0 auto 32px}}
  .price-badge{{display:inline-block;background:#22d3a0;color:#000;font-size:32px;font-weight:900;
                border-radius:14px;padding:12px 28px;margin-bottom:24px}}
  .cta-btn{{display:inline-block;background:linear-gradient(135deg,#1a6cf6,#7c3aed);color:#fff;
             font-size:20px;font-weight:800;padding:18px 48px;border-radius:14px;text-decoration:none;
             transition:transform .15s,opacity .15s;border:none;cursor:pointer}}
  .cta-btn:hover{{transform:translateY(-2px);opacity:.9}}
  .sub-cta{{font-size:12px;color:#5d7fa8;margin-top:12px}}
  .social-proof{{padding:48px 20px;text-align:center;background:#080d17;border-bottom:1px solid #1e3050}}
  .sp-inner{{max-width:700px;margin:0 auto}}
  .stars{{font-size:28px;margin-bottom:8px}}
  .sp-text{{font-size:18px;font-weight:700;margin-bottom:4px}}
  .sp-sub{{font-size:14px;color:#5d7fa8}}
  .offer{{padding:60px 20px;max-width:680px;margin:0 auto}}
  .offer h2{{font-size:28px;font-weight:800;margin-bottom:24px;text-align:center}}
  .bullets{{list-style:none;display:flex;flex-direction:column;gap:12px;margin-bottom:40px}}
  .bullets li{{display:flex;align-items:flex-start;gap:12px;font-size:16px;
                background:#0d1a2e;border:1px solid #1e3050;border-radius:10px;padding:14px}}
  .bullets li::before{{content:'✅';flex-shrink:0}}
  .guarantee{{background:#0d2a1f;border:1px solid #22d3a0;border-radius:14px;padding:24px;
              text-align:center;margin-bottom:40px}}
  .guarantee h3{{color:#22d3a0;font-size:20px;font-weight:800;margin-bottom:8px}}
  .guarantee p{{color:#94aabb;font-size:14px}}
  .final-cta{{text-align:center;padding:48px 20px;background:#080d17}}
  .urgency{{font-size:13px;color:#f59e0b;margin-top:12px;font-weight:700}}
  footer{{padding:24px;text-align:center;font-size:12px;color:#374151;border-top:1px solid #1e3050}}
</style>
</head>
<body>

<div class="hero">
  <span class="emoji">{emoji}</span>
  <h1>{product_name}</h1>
  <p>The {niche} solution that's taking over {channel}.<br>See why 10,000+ customers can't stop talking about it.</p>
  <div class="price-badge">${price:.2f}</div><br>
  <a class="cta-btn" href="{stripe_link}">Order Now — Get Yours Today</a>
  <div class="sub-cta">✅ 30-Day Guarantee &nbsp;·&nbsp; 🚚 Ships in 7 Days &nbsp;·&nbsp; 🔒 Secure Checkout</div>
</div>

<div class="social-proof">
  <div class="sp-inner">
    <div class="stars">⭐⭐⭐⭐⭐</div>
    <div class="sp-text">4.9 out of 5 stars · 10,000+ orders</div>
    <div class="sp-sub">"I was skeptical but this genuinely solved my problem. Best purchase this year." — verified buyer</div>
  </div>
</div>

<div class="offer">
  <h2>Here's Everything You Get</h2>
  <ul class="bullets">
{bullets_html}
  </ul>
  <div class="guarantee">
    <h3>🛡️ 30-Day Money-Back Guarantee</h3>
    <p>If you're not 100% satisfied for any reason, we'll refund every penny.<br>
    No forms, no hassle, no questions asked.</p>
  </div>
  <div style="text-align:center">
    <a class="cta-btn" href="{stripe_link}">Yes! I Want Mine — ${price:.2f}</a>
    <div class="urgency">⚡ Limited stock — {int(price * 3)} units left at this price</div>
  </div>
</div>

<div class="final-cta">
  <p style="font-size:22px;font-weight:800;margin-bottom:16px">Still thinking? Don't wait.</p>
  <a class="cta-btn" href="{stripe_link}">Claim Your {product_name} Now</a>
  <div class="sub-cta" style="margin-top:16px">✅ Secure · Fast Shipping · Guaranteed</div>
</div>

<footer>
  &copy; {year} — {product_name} Store. Questions? Contact us anytime.<br>
  <span style="font-size:10px">Page generated {datetime.now().strftime('%Y-%m-%d')} · Powered by Dropship OS</span>
</footer>

</body>
</html>"""

    return html, slug


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", type=str, default=None)
    parser.add_argument("--price", type=float, default=None)
    parser.add_argument("--niche", type=str, default=None)
    parser.add_argument("--stripe", type=str, default="#", help="Stripe payment link URL")
    args = parser.parse_args()

    if args.product:
        product_name = args.product
        price = args.price or 29.99
        niche = args.niche or "general"
        channel = "Pinterest Organic"
    else:
        combo = load_top_combo()
        if not combo:
            print("[AssetMachine] No decisions.json found. Run decision_engine.py first.")
            import sys; sys.exit(1)
        product_name = combo.get("product", "Top Product")
        price = float(combo.get("sell_price", 29.99))
        niche = combo.get("niche", "general")
        channel = combo.get("channel_label", "Pinterest Organic")

    OUTPUT_DIR.mkdir(exist_ok=True)
    page_html, slug = build_page(product_name, price, niche, channel, args.stripe)
    out_path = OUTPUT_DIR / f"{slug}.html"
    out_path.write_text(page_html)

    print(f"[AssetMachine] ✅ Page generated → {out_path}")
    print(f"[AssetMachine] Product: {product_name} | Price: ${price:.2f} | Niche: {niche}")
    print(f"[AssetMachine] Slug: {slug}")
    print(f"\nTo deploy to GitHub Pages:")
    print(f"  1. Copy {out_path} to your GitHub Pages repo")
    print(f"  2. git add . && git commit -m 'add {slug}' && git push")
    print(f"  3. Live at: https://yourusername.github.io/{slug}.html")
    print(f"\nTo add Stripe: rerun with --stripe 'https://buy.stripe.com/your_link'")


if __name__ == "__main__":
    main()
