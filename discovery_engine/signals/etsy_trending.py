"""Etsy collector via Playwright. Etsy 403s stdlib clients."""
import re, html, urllib.parse
from . import _common, _browser

def collect_trending(limit=25) -> list:
    if not _browser.is_available():
        return []
    body = _browser.fetch_rendered(
        "https://www.etsy.com/trending",
        wait_for_text="trending",
        timeout=25000, scroll=True,
    )
    return _parse_listings(body, limit, tag="trending")

def collect_keyword(keyword, limit=25) -> list:
    if not _browser.is_available():
        return []
    url = f"https://www.etsy.com/search?q={urllib.parse.quote(keyword)}"
    body = _browser.fetch_rendered(url, wait_for_text=keyword, timeout=25000, scroll=True)
    return _parse_listings(body, limit, tag=keyword)

def _parse_listings(body, limit, tag):
    if not body:
        return []
    out = []
    seen = set()
    # Match listing URLs like /listing/1234567/title-words
    for m in re.finditer(r'href="(https?://www\.etsy\.com)?(/(?:[a-z-]+/)?listing/(\d{6,12})[^"]*)"', body):
        lid = m.group(3)
        if lid in seen: continue
        # Title from nearby alt/title/aria-label attribute
        nearby = body[max(0,m.start()-200):m.start()+1500]
        title_m = re.search(r'(?:alt|aria-label|title)="([^"]{6,300})"', nearby)
        if not title_m:
            continue
        title = html.unescape(title_m.group(1)).strip()
        # skip generic UI labels
        if any(s in title.lower() for s in ("etsy", "search", "filter", "log in", "sign in", "menu")):
            continue
        seen.add(lid)
        url = (m.group(1) or "https://www.etsy.com") + m.group(2)
        out.append({
            "platform": "etsy",
            "source_url": url, "id": lid,
            "title": title, "text": title,
            "score": limit - len(out),
            "tags": [tag] if tag != "trending" else [],
            "buyer_intent_hits": [],
        })
        if len(out) >= limit: break
    return out