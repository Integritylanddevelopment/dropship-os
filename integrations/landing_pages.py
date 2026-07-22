import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""Per-product landing pages: one-page store + Stripe payment link.

Flow per product:
  1. Create Stripe product + price + payment link (plain REST, no SDK needed)
  2. Render a mobile-first one-pager HTML with BUY NOW -> payment link
  3. Upload HTML to the public GitHub repo -> served by GitHub Pages

Env: STRIPE_SECRET_KEY, GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_PAGES_REPO
"""
import os
import json
import base64
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).parent.parent
    load_dotenv(_root / ".env")
    load_dotenv(_root / ".env.local", override=True)
except ImportError:
    pass

STRIPE_API = "https://api.stripe.com/v1"
GH_API = "https://api.github.com"


# ── Stripe (REST, form-encoded) ──────────────────────────────────────────

def _stripe_post(path: str, fields: dict) -> dict:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        return {"error": "STRIPE_SECRET_KEY not set"}
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(f"{STRIPE_API}/{path}", data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}


def create_payment_link(product_name: str, price_usd: float,
                        image_url: str = "", description: str = "") -> dict:
    """Create Stripe product + price + payment link. Returns {url, ids} or {error}."""
    pf = {"name": product_name[:250]}
    if description:
        pf["description"] = description[:350]
    if image_url:
        pf["images[0]"] = image_url
    prod = _stripe_post("products", pf)
    if "error" in prod or not prod.get("id"):
        return {"error": str(prod.get("error", prod))[:200]}

    price = _stripe_post("prices", {
        "product": prod["id"],
        "unit_amount": int(round(price_usd * 100)),
        "currency": "usd",
    })
    if "error" in price or not price.get("id"):
        return {"error": str(price.get("error", price))[:200]}

    link = _stripe_post("payment_links", {
        "line_items[0][price]": price["id"],
        "line_items[0][quantity]": 1,
        "shipping_address_collection[allowed_countries][0]": "US",
        "shipping_address_collection[allowed_countries][1]": "CA",
        # Phone required: the supplier (CJ) needs it on the shipping label
        "phone_number_collection[enabled]": "true",
    })
    if "error" in link or not link.get("url"):
        return {"error": str(link.get("error", link))[:200]}

    return {
        "url": link["url"],
        "payment_link_id": link.get("id", ""),
        "product_id": prod["id"],
        "price_id": price["id"],
    }


# ── GitHub upload + Pages ────────────────────────────────────────────────

def _gh_cfg():
    tok = os.getenv("GITHUB_TOKEN", "")
    user = os.getenv("GITHUB_USERNAME", "")
    repo = os.getenv("GITHUB_PAGES_REPO", "")
    if not (tok and user and repo):
        raise RuntimeError("GitHub not configured (GITHUB_TOKEN/USERNAME/PAGES_REPO)")
    return tok, user, repo


def _gh_api(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ShipStack-Landing/1.0",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def upload_text(repo_path: str, content: str, message: str = "page") -> bool:
    tok, user, repo = _gh_cfg()
    url = f"{GH_API}/repos/{user}/{repo}/contents/{repo_path}"
    sha = None
    code, existing = _gh_api("GET", f"{url}?ref=main", tok)
    if code == 200:
        sha = existing.get("sha")
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    code, _ = _gh_api("PUT", url, tok, payload)
    return code in (200, 201)


def ensure_pages_enabled() -> str:
    """Enable GitHub Pages on the repo (main branch, root). Returns the site base URL."""
    tok, user, repo = _gh_cfg()
    base = f"https://{user.lower()}.github.io/{repo}"
    code, resp = _gh_api("GET", f"{GH_API}/repos/{user}/{repo}/pages", tok)
    if code == 200:
        return resp.get("html_url", base).rstrip("/")
    # create
    code, resp = _gh_api("POST", f"{GH_API}/repos/{user}/{repo}/pages", tok,
                         {"source": {"branch": "main", "path": "/"}})
    return base


# ── Landing page HTML ────────────────────────────────────────────────────

def render_landing_html(product_name: str, photo_url: str, retail_price: float,
                        compare_at: float, benefit: str, bullets: list,
                        buy_url: str, headline: str = "", paragraph: str = "",
                        quote: str = "") -> str:
    save_pct = int(round((1 - retail_price / compare_at) * 100)) if compare_at > retail_price > 0 else 0
    bullets_html = "\n".join(f'<li>{b}</li>' for b in bullets[:6])
    photo_html = (f'<img class="hero" src="{photo_url}" alt="{product_name}">'
                  if photo_url else "")
    save_html = (f'<span class="cmp">${compare_at:,.2f}</span>'
                 f'<span class="save">SAVE {save_pct}%</span>' if save_pct else "")
    headline_html = f'<p class="hook">{headline}</p>' if headline else ""
    story_html = f'<p class="story">{paragraph}</p>' if paragraph else ""
    quote_html = (f'<div class="quote">&ldquo;{quote}&rdquo;<span> — buyer comment found online</span></div>'
                  if quote else "")
    stack_total = compare_at if compare_at > retail_price else retail_price * 1.5
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{product_name}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',system-ui,sans-serif; }}
  body {{ background:#f7f8fa; color:#181c23; }}
  .page {{ max-width:520px; margin:0 auto; background:#fff; min-height:100vh; }}
  .hero {{ width:100%; display:block; }}
  .body {{ padding:22px 22px 46px; }}
  .badge {{ display:inline-block; background:#ff5252; color:#fff; font-size:12px; font-weight:700;
           letter-spacing:1px; padding:6px 14px; border-radius:999px; margin-bottom:12px; }}
  .hook {{ font-size:22px; font-weight:800; color:#06897c; margin-bottom:6px; line-height:1.25; }}
  h1 {{ font-size:27px; line-height:1.2; margin-bottom:10px; }}
  .benefit {{ color:#6e7682; font-size:16px; margin-bottom:14px; }}
  .story {{ font-size:15.5px; color:#3a4150; line-height:1.65; margin-bottom:18px; }}
  .price-row {{ display:flex; align-items:center; gap:12px; margin-bottom:18px; }}
  .price {{ font-size:38px; font-weight:800; }}
  .cmp {{ color:#9aa2ae; text-decoration:line-through; font-size:20px; }}
  .save {{ background:#ff5252; color:#fff; font-size:13px; font-weight:700; padding:5px 12px; border-radius:999px; }}
  ul {{ list-style:none; margin-bottom:20px; }}
  li {{ padding:8px 0 8px 30px; position:relative; font-size:15.5px; color:#3a4150; }}
  li:before {{ content:'✓'; position:absolute; left:2px; color:#06b6a4; font-weight:800; }}
  .quote {{ background:#f2faf9; border-left:4px solid #06b6a4; padding:14px 16px; border-radius:0 12px 12px 0;
           font-size:15.5px; font-style:italic; color:#2a4a46; margin-bottom:20px; }}
  .quote span {{ display:block; font-style:normal; font-size:12.5px; color:#7a948f; margin-top:6px; }}
  .stack {{ border:1.5px solid #e4e9ee; border-radius:14px; padding:16px 18px; margin-bottom:22px; }}
  .stack h3 {{ font-size:13px; text-transform:uppercase; letter-spacing:1px; color:#8a94a2; margin-bottom:10px; }}
  .stack .row {{ display:flex; justify-content:space-between; font-size:14.5px; padding:6px 0; color:#3a4150; }}
  .stack .row.total {{ border-top:1.5px solid #e4e9ee; margin-top:8px; padding-top:12px; font-weight:800; color:#181c23; font-size:16px; }}
  .stack .was {{ color:#9aa2ae; text-decoration:line-through; margin-right:8px; }}
  .buy {{ display:block; background:#06b6a4; color:#fff; text-align:center; font-size:20px; font-weight:800;
         padding:18px; border-radius:14px; text-decoration:none; letter-spacing:.5px;
         box-shadow:0 6px 18px rgba(6,182,164,.35); }}
  .buy:active {{ transform:translateY(1px); }}
  .trust {{ text-align:center; color:#9aa2ae; font-size:13px; margin-top:12px; margin-bottom:26px; }}
  .faq {{ border-top:1px solid #edf0f3; padding-top:18px; }}
  .faq h3 {{ font-size:15px; margin-bottom:12px; }}
  .faq p {{ font-size:13.5px; color:#6e7682; line-height:1.6; margin-bottom:12px; }}
  .faq b {{ color:#3a4150; }}
</style></head>
<body><div class="page">
  {photo_html}
  <div class="body">
    <span class="badge">TRENDING NOW</span>
    {headline_html}
    <h1>{product_name}</h1>
    <p class="benefit">{benefit}</p>
    <div class="price-row">
      <span class="price">${retail_price:,.2f}</span>
      {save_html}
    </div>
    <a class="buy" href="{buy_url}">BUY NOW — SECURE CHECKOUT</a>
    <p class="trust">Powered by Stripe · Card details never touch our servers</p>
    {story_html}
    <ul>{bullets_html}</ul>
    {quote_html}
    <div class="stack">
      <h3>What you get today</h3>
      <div class="row"><span>{product_name}</span><span><span class="was">${stack_total:,.2f}</span></span></div>
      <div class="row"><span>Tracked shipping to your door</span><span>Included</span></div>
      <div class="row"><span>30-day return protection</span><span>Included</span></div>
      <div class="row total"><span>Your price</span><span>${retail_price:,.2f}</span></div>
    </div>
    <div class="faq">
      <h3>Common questions</h3>
      <p><b>How fast does it ship?</b><br>Orders process in 1-2 business days. Typical delivery is 7-15 days, with a tracking number the whole way.</p>
      <p><b>What if it's not for me?</b><br>You have a 30-day window to return unused items. No hoops.</p>
      <p><b>Is checkout safe?</b><br>Payment runs through Stripe — the same processor used by millions of stores. We never see your card number.</p>
    </div>
    <a class="buy" style="margin-top:22px" href="{buy_url}">GET YOURS — ${retail_price:,.2f}</a>
    <div style="border-top:1px solid #edf0f3; margin-top:30px; padding-top:18px; text-align:center;
                font-size:12.5px; color:#9aa2ae; line-height:1.9">
      <b style="color:#6e7682">Integrity Products USA</b><br>
      Support: <a style="color:#06897c" href="mailto:support@integrityproductsusa.com">support@integrityproductsusa.com</a> · 945-312-6709<br>
      <a style="color:#9aa2ae" href="/dropship-os/legal/privacy.html">Privacy Policy</a> &nbsp;·&nbsp;
      <a style="color:#9aa2ae" href="/dropship-os/legal/terms.html">Terms of Service</a><br>
      © 2026 Integrity Products USA. All rights reserved.
    </div>
  </div>
</div></body></html>"""


def publish_landing_page(product_id: str, html: str) -> str:
    """Upload landing HTML, return the public Pages URL."""
    base = ensure_pages_enabled()
    path = f"landing/{product_id}.html"
    ok = upload_text(path, html, message=f"landing: {product_id}")
    if not ok:
        raise RuntimeError("GitHub upload failed")
    return f"{base}/{path}"
