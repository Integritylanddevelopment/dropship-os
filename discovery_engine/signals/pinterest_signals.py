"""Pinterest collector via Playwright (stdlib fetches got 0 because of XHR-loaded data)."""
import re, urllib.parse, json
from . import _common, _browser

def collect_keyword(keyword, limit=25) -> list:
    if not _browser.is_available():
        # Fall back to stdlib (returns 0 but keeps signature stable)
        return _stdlib_fallback(keyword, limit)
    url = f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(keyword)}"
    body = _browser.fetch_rendered(url, wait_for_text=keyword, timeout=25000, scroll=True)
    if not body:
        return []
    return _parse_pins(body, keyword, limit)

def _stdlib_fallback(keyword, limit):
    body = _common.fetch(
        f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(keyword)}",
        timeout=25, headers={"Accept":"text/html"})
    if not body:
        return []
    return _parse_pins(body, keyword, limit)

def _parse_pins(body, keyword, limit):
    out = []
    seen = set()
    # Try __PWS_INITIAL_PROPS__ JSON walk
    m = re.search(r'id="__PWS_INITIAL_PROPS__"[^>]*>(\{.+?\})</script>', body, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            _walk_for_pins(data, out, seen, keyword, limit)
        except Exception:
            pass
    if not out:
        # Broad fallback: any /pin/<id>/ URL with nearby alt text
        for m in re.finditer(r'/pin/(\d{8,20})/', body):
            pid = m.group(1)
            if pid in seen: continue
            nearby = body[max(0,m.start()-100):m.start()+1500]
            title_m = re.search(r'alt="([^"]{4,300})"', nearby)
            title = title_m.group(1).strip() if title_m else f"Pin {pid}"
            seen.add(pid)
            out.append({
                "platform":"pinterest", "source_url":f"https://www.pinterest.com/pin/{pid}/",
                "id":pid, "title":title[:300], "text":title[:1000],
                "score":limit-len(out), "saves":0, "tags":[keyword],
                "buyer_intent_hits":_common.extract_buyer_intent(title),
            })
            if len(out) >= limit: break
    return out

def _walk_for_pins(obj, out, seen, keyword, limit):
    if len(out) >= limit: return
    if isinstance(obj, dict):
        pid = obj.get("id")
        if isinstance(pid, str) and pid.isdigit() and len(pid) >= 6 \
                and ("grid_title" in obj or "description" in obj):
            if pid not in seen:
                title = (obj.get("grid_title") or obj.get("description") or obj.get("title") or "").strip()
                if title and len(title) >= 3:
                    seen.add(pid)
                    out.append({
                        "platform":"pinterest", "source_url":f"https://www.pinterest.com/pin/{pid}/",
                        "id":pid, "title":title[:300], "text":title[:1000],
                        "score":limit-len(out), "saves":int(obj.get("repin_count") or 0),
                        "tags":[keyword],
                        "buyer_intent_hits":_common.extract_buyer_intent(title),
                    })
                    if len(out) >= limit: return
        for v in obj.values():
            _walk_for_pins(v, out, seen, keyword, limit)
            if len(out) >= limit: return
    elif isinstance(obj, list):
        for v in obj:
            _walk_for_pins(v, out, seen, keyword, limit)
            if len(out) >= limit: return