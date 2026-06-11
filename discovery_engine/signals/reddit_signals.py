"""Reddit signal collector via api.pullpush.io (Pushshift mirror). No auth."""
from typing import Iterable
import urllib.parse, time
from . import _common

def collect_subreddit(subreddit: str, limit: int = 50, sort: str = "score") -> list[dict]:
    """Return list of normalized signal dicts from r/<subreddit>. sort in {score, created_utc}."""
    url = f"https://api.pullpush.io/reddit/search/submission/?subreddit={urllib.parse.quote(subreddit)}&sort={sort}&size={limit}"
    data = _common.fetch_json(url, timeout=20)
    items = data.get("data") or []
    signals = []
    for p in items:
        text = (p.get("title") or "") + "\n" + (p.get("selftext") or "")
        signals.append({
            "platform": "reddit",
            "source_url": f"https://reddit.com{p.get('permalink','')}",
            "id": p.get("id"),
            "title": p.get("title"),
            "text": text[:2000],
            "score": int(p.get("score") or 0),
            "comments": int(p.get("num_comments") or 0),
            "shares": 0,
            "saves": 0,
            "views": 0,
            "author": p.get("author"),
            "created_utc": p.get("created_utc"),
            "subreddit": subreddit,
            "tags": [],
            "buyer_intent_hits": _common.extract_buyer_intent(text),
        })
    return signals

def collect_keyword(keyword: str, limit: int = 50) -> list[dict]:
    """Search Reddit-wide for a keyword via Pullpush."""
    url = f"https://api.pullpush.io/reddit/search/submission/?q={urllib.parse.quote(keyword)}&sort=score&size={limit}"
    data = _common.fetch_json(url, timeout=20)
    items = data.get("data") or []
    signals = []
    for p in items:
        text = (p.get("title") or "") + "\n" + (p.get("selftext") or "")
        signals.append({
            "platform": "reddit",
            "source_url": f"https://reddit.com{p.get('permalink','')}",
            "id": p.get("id"),
            "title": p.get("title"),
            "text": text[:2000],
            "score": int(p.get("score") or 0),
            "comments": int(p.get("num_comments") or 0),
            "author": p.get("author"),
            "created_utc": p.get("created_utc"),
            "subreddit": p.get("subreddit"),
            "tags": [keyword],
            "buyer_intent_hits": _common.extract_buyer_intent(text),
        })
    return signals