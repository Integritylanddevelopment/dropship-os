"""Shared HTTP helpers + throttling for signal collectors. Stdlib only."""
import urllib.request, urllib.error, urllib.parse, http.cookiejar, json, re, time, gzip, random
from typing import Optional

CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# ---------- Throttle / batch jitter ----------
# Tracks last-hit timestamp per host so consecutive requests to the same host
# get a longer minimum pause. Per-host floor and per-call random jitter.
_LAST_HIT: dict[str, float] = {}

PER_HOST_FLOOR_SEC = 1.5   # min gap between hits to the SAME host
GLOBAL_FLOOR_SEC   = 0.3   # min gap between ANY two hits
JITTER_RANGE       = (0.4, 1.6)   # random extra pause added to every call

def throttle(host_hint: str = ""):
    """Pause so we don't hammer a single host. Call BEFORE each fetch.

    host_hint: a string identifying the host (e.g. 'reddit.com'). Same host =
    longer wait. Empty = only the global floor + jitter applies."""
    now = time.time()
    jitter = random.uniform(*JITTER_RANGE)
    if host_hint:
        last = _LAST_HIT.get(host_hint, 0)
        wait = max(PER_HOST_FLOOR_SEC - (now - last), 0)
    else:
        wait = 0
    wait = max(wait + jitter, GLOBAL_FLOOR_SEC)
    time.sleep(wait)
    if host_hint:
        _LAST_HIT[host_hint] = time.time()

def _opener_with_cookies():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPRedirectHandler(),
    )
    op.addheaders = list(DEFAULT_HEADERS.items())
    return op

def _host_from_url(u: str) -> str:
    try:
        return urllib.parse.urlparse(u).netloc.lower()
    except Exception:
        return ""

def fetch(url: str, headers: Optional[dict] = None, timeout: int = 20, retries: int = 2) -> str:
    throttle(_host_from_url(url))
    opener = _opener_with_cookies()
    if headers:
        opener.addheaders = list({**DEFAULT_HEADERS, **headers}.items())
    last_err = None
    for attempt in range(retries + 1):
        try:
            with opener.open(url, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            if attempt < retries:
                # backoff with jitter
                time.sleep((1.5 ** attempt) + random.uniform(0.2, 0.8))
    return ""

def fetch_json(url: str, headers: Optional[dict] = None, timeout: int = 20) -> dict:
    body = fetch(url, headers, timeout)
    if not body:
        return {}
    if body.startswith(")]}'"):
        body = body.split("\n", 1)[1] if "\n" in body else body[5:]
    try:
        return json.loads(body)
    except Exception:
        return {}

BUYER_INTENT_PHRASES = [
    # Direct purchase intent
    "where can i buy", "where to buy", "link please", "drop the link", "need this",
    "amazon link", "tiktok made me buy", "tiktok shop link", "does this ship",
    "is this available", "where did you get", "what brand", "how much",
    "ordering this", "buying this", "added to cart", "i need this in my life",
    "shut up and take my money", "comment for link", "link in bio",
    # Recommendation-seeking (strong purchase signal on Reddit)
    "worth it", "worth the money", "worth buying", "worth the price",
    "recommend", "which one should i", "best one",
    "just bought", "just ordered", "just got mine", "finally bought",
    "anyone tried", "anyone have", "anyone use",
    "thinking about buying", "thinking of getting", "should i buy",
    "should i get", "want to buy", "looking to buy",
    "looking for a", "looking for recommendations",
    # Price/deal hunting
    "on sale", "coupon code", "discount code", "promo code",
    "cheaper alternative", "budget friendly", "affordable",
    # Post-purchase validation (confirms demand exists)
    "game changer", "life changer", "changed my life",
    "best purchase", "best thing i bought", "so glad i bought",
    "highly recommend", "must have", "can't live without",
    "obsessed with", "swear by",
]

def extract_buyer_intent(text: str) -> list:
    if not text:
        return []
    t = text.lower()
    return [p for p in BUYER_INTENT_PHRASES if p in t]