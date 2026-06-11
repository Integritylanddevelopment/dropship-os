"""YouTube search via ytInitialData JSON. Walks the nested response to find
all videoRenderer dicts (which contain videoId, title, viewCountText, ownerText).
"""
import urllib.parse, re, json
from . import _common

def collect_keyword(keyword, limit=25) -> list:
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}"
    body = _common.fetch(url, timeout=20)
    if not body:
        return []
    # Extract the ytInitialData JSON object - it spans up to `;</script>`
    m = re.search(r"var ytInitialData = (\{.+?\});</script>", body, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    out = []
    seen = set()
    _walk_for_videos(data, out, seen, keyword, limit)
    return out

def _walk_for_videos(obj, out, seen, keyword, limit):
    """Recursively descend looking for videoRenderer dicts."""
    if len(out) >= limit:
        return
    if isinstance(obj, dict):
        vr = obj.get("videoRenderer")
        if isinstance(vr, dict):
            _extract(vr, out, seen, keyword)
            if len(out) >= limit: return
        for v in obj.values():
            _walk_for_videos(v, out, seen, keyword, limit)
            if len(out) >= limit: return
    elif isinstance(obj, list):
        for v in obj:
            _walk_for_videos(v, out, seen, keyword, limit)
            if len(out) >= limit: return

def _extract(vr, out, seen, keyword):
    vid = vr.get("videoId")
    if not vid or vid in seen:
        return
    title_runs = (vr.get("title") or {}).get("runs") or []
    title = "".join((r.get("text") or "") for r in title_runs).strip()
    if not title:
        title = (vr.get("title") or {}).get("simpleText", "")
    if not title:
        return
    view_text = ((vr.get("viewCountText") or {}).get("simpleText") or
                 "".join((r.get("text") or "") for r in (vr.get("viewCountText") or {}).get("runs", [])))
    views = _parse_count(view_text)
    chan = ""
    if "ownerText" in vr:
        chan_runs = (vr["ownerText"] or {}).get("runs") or []
        chan = "".join((r.get("text") or "") for r in chan_runs)
    pub = (vr.get("publishedTimeText") or {}).get("simpleText", "")
    seen.add(vid)
    out.append({
        "platform":"youtube",
        "source_url":f"https://www.youtube.com/watch?v={vid}",
        "id":vid, "title":title, "text":title,
        "views":views, "score":views, "comments":0,
        "author":chan, "published":pub, "tags":[keyword],
        "buyer_intent_hits":_common.extract_buyer_intent(title),
    })

def _parse_count(s):
    if not s: return 0
    s = s.lower().replace(",", "").replace("views", "").strip()
    try:
        if s.endswith("k"): return int(float(s[:-1]) * 1000)
        if s.endswith("m"): return int(float(s[:-1]) * 1000000)
        if s.endswith("b"): return int(float(s[:-1]) * 1000000000)
        return int(float(s))
    except: return 0