"""Reddit signal collector via api.pullpush.io (Pushshift mirror).

NOTE: Reddit blocks unauthenticated JSON API access (403 Blocked as of 2026-07).
Using Pullpush as primary source. Data is stale (~2023) but usable for product
signal discovery. When Reddit OAuth is set up (task #46), this module should
switch to Reddit's authenticated API for live data."""
import urllib.parse, time
from . import _common

def _parse_pullpush(p: dict, subreddit: str = "", tags: list = None) -> dict:
    """Normalize a Pullpush post dict into a signal dict."""
    title = p.get("title") or ""
    selftext = p.get("selftext") or ""
    text = f"{title}\n{selftext}"[:2000]
    return {
        "platform": "reddit",
        "source_url": f"https://reddit.com{p.get('permalink', '')}",
        "id": p.get("id"),
        "title": title,
        "text": text,
        "score": int(p.get("score") or 0),
        "comments": int(p.get("num_comments") or 0),
        "shares": 0,
        "saves": 0,
        "views": 0,
        "author": p.get("author"),
        "created_utc": p.get("created_utc"),
        "subreddit": subreddit or p.get("subreddit", ""),
        "tags": tags or [],
        "buyer_intent_hits": _common.extract_buyer_intent(text),
    }

def collect_subreddit(subreddit: str, limit: int = 50, sort: str = "score") -> list[dict]:
    """Return list of normalized signal dicts from r/<subreddit>."""
    url = (f"https://api.pullpush.io/reddit/search/submission/"
           f"?subreddit={urllib.parse.quote(subreddit)}&sort={sort}&size={limit}")
    data = _common.fetch_json(url, timeout=20)
    items = data.get("data") or []
    return [_parse_pullpush(p, subreddit=subreddit) for p in items[:limit]]

def collect_keyword(keyword: str, limit: int = 50) -> list[dict]:
    """Search Reddit-wide for a keyword via Pullpush."""
    url = (f"https://api.pullpush.io/reddit/search/submission/"
           f"?q={urllib.parse.quote(keyword)}&sort=score&size={limit}")
    data = _common.fetch_json(url, timeout=20)
    items = data.get("data") or []
    return [_parse_pullpush(p, tags=[keyword]) for p in items[:limit]]
