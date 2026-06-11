"""AliExpress supplier search (free-tier scrape with browser fallback)."""
import urllib.parse, re, json
from ..signals import _common
try:
    from ..signals import _browser
except Exception:
    _browser = None

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def search(keyword, limit=15):
    url = "https://www.aliexpress.com/wholesale-" + urllib.parse.quote(keyword.replace(" ", "-")) + ".html?SortType=total_tranpro_desc"
    body = _common.fetch(url, timeout=20, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"})
    if not body or len(body) < 5000:
        if _browser is not None and _browser.is_available():
            body = _browser.fetch_rendered(url, timeout=25000, scroll=True)
    if not body:
        return []
    return _parse(body, keyword, limit)

def _parse(body, keyword, limit):
    out, seen = [], set()
    m = re.search(r"window\.runParams\s*=\s*(\{.+?\});", body, re.DOTALL)
    if m:
        try:
            _walk(json.loads(m.group(1)), out, seen, limit)
        except Exception:
            pass
    if len(out) >= limit:
        return out[:limit]
    for it_m in re.finditer(r"/item/(\d{10,18})\.html", body):
        pid = it_m.group(1)
        if pid in seen:
            continue
        ctx = body[max(0, it_m.start()-400): it_m.start()+1200]
        title = _first(ctx, [r'"subject"\s*:\s*"([^"]{6,300})"', r'title="([^"]{6,300})"', r'alt="([^"]{6,300})"', r'>([^<]{6,200})</a>'])
        price = _first(ctx, [r'"minPrice"\s*:\s*"?(\d+\.\d+)', r'"actMinPrice"\s*:\s*"?(\d+\.\d+)', r'US\s*\$\s*(\d+\.\d+)', r'\$(\d+\.\d+)'])
        orders = _first(ctx, [r'"tradeAmount"\s*:\s*"?(\d+)', r'(\d{2,7})\s+sold', r'(\d{2,7})\s+orders'])
        if not title:
            continue
        try: uc = float(price) if price else 0.0
        except Exception: uc = 0.0
        try: rc = int(orders) if orders else 0
        except Exception: rc = 0
        seen.add(pid)
        out.append({
            "supplier": "aliexpress",
            "supplier_url": f"https://www.aliexpress.com/item/{pid}.html",
            "id": pid, "title": title.strip()[:300], "image": "",
            "unit_cost": uc, "moq": 1,
            "shipping_options": ["AliExpress Standard", "ePacket"],
            "supplier_rating": 0.0, "review_count": rc,
            "dropship_available": True, "blind_dropship": False,
            "categories": "", "raw": {"orders": orders, "price": price},
        })
        if len(out) >= limit:
            break
    return out

def _walk(obj, out, seen, limit):
    if len(out) >= limit:
        return
    if isinstance(obj, dict):
        pid = obj.get("productId") or obj.get("itemId") or obj.get("id")
        title = obj.get("title") or obj.get("subject")
        mp = obj.get("minPrice") or obj.get("actMinPrice")
        if pid and isinstance(title, str) and len(title) > 5 and str(pid).isdigit() and len(str(pid)) >= 10:
            if pid not in seen:
                seen.add(pid)
                try: uc = float(mp if isinstance(mp, (int, float, str)) else 0)
                except Exception: uc = 0.0
                out.append({
                    "supplier":"aliexpress",
                    "supplier_url":f"https://www.aliexpress.com/item/{pid}.html",
                    "id":str(pid), "title":title.strip()[:300],
                    "image": obj.get("image") or obj.get("mainImage") or "",
                    "unit_cost":uc, "moq":1,
                    "shipping_options":["AliExpress Standard","ePacket"],
                    "supplier_rating":float(obj.get("averageStar") or 0),
                    "review_count":int(obj.get("tradeAmount") or 0),
                    "dropship_available":True, "blind_dropship":False,
                    "categories":"", "raw":{},
                })
                if len(out) >= limit:
                    return
        for v in obj.values():
            _walk(v, out, seen, limit)
            if len(out) >= limit:
                return
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, out, seen, limit)
            if len(out) >= limit:
                return

def _first(text, pats):
    for pat in pats:
        m = re.search(pat, text)
        if m: return m.group(1)
    return ""