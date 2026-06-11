"""Google Trends via /trending/rss?geo=US - still works without auth."""
import re, html as _html
from . import _common

def collect_daily(geo="US") -> list:
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    body = _common.fetch(url, timeout=20, headers={"Accept":"application/rss+xml, application/xml, text/xml"})
    if not body: return []
    out = []
    for m in re.finditer(r"<item>(.+?)</item>", body, re.DOTALL):
        item = m.group(1)
        title_m = re.search(r"<title>\s*<!\[CDATA\[(.+?)\]\]>\s*</title>|<title>([^<]+)</title>", item, re.DOTALL)
        title = ""
        if title_m: title = (title_m.group(1) or title_m.group(2) or "").strip()
        traffic_m = re.search(r"<ht:approx_traffic>([^<]+)</ht:approx_traffic>", item)
        traffic = traffic_m.group(1).strip() if traffic_m else ""
        link_m = re.search(r"<link>\s*([^<]+)\s*</link>", item)
        link = link_m.group(1).strip() if link_m else ""
        if not title: continue
        out.append({
            "platform":"google_trends", "source_url":link,
            "title":_html.unescape(title), "text":_html.unescape(title),
            "traffic":traffic, "tags":[title.lower()],
            "rising_score":_traffic_to_score(traffic), "buyer_intent_hits":[],
        })
    return out

def _traffic_to_score(s):
    if not s: return 0
    s = s.replace("+","").strip().upper()
    try:
        if s.endswith("M"): return int(float(s[:-1])*1000000)
        if s.endswith("K"): return int(float(s[:-1])*1000)
        return int(s)
    except: return 0