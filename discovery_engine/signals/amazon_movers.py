"""Amazon Movers & Shakers - 2024+ markup."""
import re, html, urllib.parse
from . import _common

CATEGORIES = ["pet-supplies","home-garden","kitchen","beauty","health-personal-care",
              "office-products","electronics","toys-and-games","sports-outdoors","automotive"]

def collect_category(category="pet-supplies", limit=25) -> list:
    url = f"https://www.amazon.com/gp/movers-and-shakers/{category}/"
    body = _common.fetch(url, timeout=25, headers={"Referer":"https://www.amazon.com/"})
    if not body: return []
    out = []
    seen = set()
    for m in re.finditer(r'href="(/[^"]*?/dp/([A-Z0-9]{10})[^"]*)"', body):
        href, asin = m.group(1), m.group(2)
        if asin in seen: continue
        nearby = body[m.start():m.start()+3500]
        title = ""
        title_m = re.search(r'<img[^>]+alt="([^"]+)"', nearby)
        if title_m: title = html.unescape(title_m.group(1)).strip()
        if not title or len(title) < 4:
            t2 = re.search(r'class="[^"]*p13n-sc-truncate[^"]*"[^>]*>\s*([^<]+)', nearby)
            if t2: title = html.unescape(t2.group(1)).strip()
        if not title or len(title) < 4:
            t3 = re.search(r'class="[^"]*line-clamp[^"]*"[^>]*>([^<]{4,200})', nearby)
            if t3: title = html.unescape(t3.group(1)).strip()
        if not title or len(title) < 4: continue
        seen.add(asin)
        out.append({
            "platform":"amazon_movers", "source_url":f"https://www.amazon.com/dp/{asin}",
            "id":asin, "title":title, "text":title, "category":category,
            "score":limit-len(out), "rank_in_movers":len(out)+1,
            "tags":[category], "buyer_intent_hits":[],
        })
        if len(out) >= limit: break
    return out

def collect_all_categories(limit_per_cat=10) -> list:
    out = []
    for cat in CATEGORIES:
        out.extend(collect_category(cat, limit=limit_per_cat))
    return out