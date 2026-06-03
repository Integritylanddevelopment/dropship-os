#!/usr/bin/env python3
"""
Product Onboarding Agent — ShipStack AI
========================================
Fires when a product is pushed from the decision engine to the shop.
4 live steps — NO stubs, NO placeholders, NO mocked data.

  A. Pull full product data from Zendrop API (live API key)
  B. Scrape internet collateral:
       - Amazon       -> Playwright headless (bypasses bot blocks)
       - Google/DDG   -> requests + BeautifulSoup (already working in engine)
       - YouTube      -> Data API v3 (OAuth2 refresh token, same as social_poster.py)
       - Reddit       -> public JSON API (no auth)
       - TikTok       -> Playwright headless (JS-rendered, only real option)
  C. Quinn (port 8765) -> marketing copy. Falls back to Ollama. Raises if both offline.
  D. Write prometheus_ready.json for Prometheus video engine.

PREREQUISITES:
  pip install playwright==1.44.0 --break-system-packages
  playwright install chromium

  YouTube Data API v3 must be ENABLED in Google Cloud Console:
  https://console.cloud.google.com/apis/library/youtube.googleapis.com
  (The refresh token already has the right scopes — youtube + youtube.upload)

Usage (standalone CLI):
  python agents/product_onboarding_agent.py "Self-Cleaning Lint Brush" [zendrop_id]
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# ── Config ─────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent.parent
COLLATERAL_DIR = BASE_DIR / "data" / "product_collateral"
COLLATERAL_DIR.mkdir(parents=True, exist_ok=True)

ZENDROP_API_KEY       = os.getenv("ZENDROP_API_KEY")
ZENDROP_BASE          = "https://app.zendrop.com/api"
YOUTUBE_CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
QUINN_BASE            = f"http://{os.getenv('QUINN_HOST', 'localhost')}:{os.getenv('QUINN_PORT', '8765')}"
OLLAMA_BASE           = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}"
OLLAMA_MODEL          = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Optional imports ───────────────────────────────────────────────────────
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# =========================================================================
# Helpers
# =========================================================================

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip())[:60].strip("_")


def get_product_dir(slug: str) -> Path:
    d = COLLATERAL_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_logger(slug: str) -> logging.Logger:
    log_path = get_product_dir(slug) / "onboarding.log"
    logger   = logging.getLogger(f"onboarding.{slug}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_path)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter("[Onboarding] %(message)s"))
        logger.addHandler(ch)
    return logger


def _extract_json(text: str) -> dict | None:
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return None


def _get_youtube_access_token(logger) -> str | None:
    """
    Exchange stored refresh token for a fresh OAuth2 access token.
    Same pattern as social_poster.py YouTubePoster._get_access_token().
    Requires YouTube Data API v3 enabled at:
    https://console.cloud.google.com/apis/library/youtube.googleapis.com
    """
    if not (YOUTUBE_REFRESH_TOKEN and YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET):
        logger.warning("  [YouTube] OAuth credentials missing from .env")
        return None
    if not HAS_REQUESTS:
        return None
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "refresh_token": YOUTUBE_REFRESH_TOKEN,
                "grant_type":    "refresh_token",
            },
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and "access_token" in data:
            return data["access_token"]
        else:
            logger.error(
                f"  [YouTube] Token exchange failed: {resp.status_code} {data}. "
                f"Ensure YouTube Data API v3 is enabled at "
                f"https://console.cloud.google.com/apis/library/youtube.googleapis.com"
            )
            return None
    except Exception as e:
        logger.error(f"  [YouTube] Token exchange error: {e}")
        return None


# =========================================================================
# Playwright scrapers (async — called via asyncio.run() from sync steps)
# =========================================================================

async def _playwright_scrape_amazon(product_name: str, logger) -> list:
    """
    Scrape Amazon search results using Playwright headless Chromium.
    Bypasses bot detection that blocks plain requests.
    Returns list of {title, price, rating, bullet_points, aplus_snippet}.
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright not installed. Run: "
            "pip install playwright==1.44.0 --break-system-packages && playwright install chromium"
        )

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=SCRAPE_HEADERS["User-Agent"],
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        # Remove navigator.webdriver fingerprint
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = await ctx.new_page()

        try:
            url = f"https://www.amazon.com/s?k={requests.utils.quote(product_name)}&ref=nb_sb_noss"
            logger.info(f"  [Amazon/Playwright] Loading: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # let lazy-load content settle

            cards = await page.query_selector_all('[data-component-type="s-search-result"]')
            logger.info(f"  [Amazon/Playwright] Found {len(cards)} product cards")

            for card in cards[:8]:
                try:
                    title_el  = await card.query_selector("h2 a span")
                    price_el  = await card.query_selector(".a-price .a-offscreen")
                    rating_el = await card.query_selector("[aria-label*='stars']")
                    bullet_els = await card.query_selector_all(".a-list-item")

                    title   = (await title_el.inner_text()).strip()  if title_el  else ""
                    price   = (await price_el.inner_text()).strip()  if price_el  else ""
                    rating  = await rating_el.get_attribute("aria-label") if rating_el else ""
                    bullets = []
                    for b in bullet_els[:6]:
                        txt = (await b.inner_text()).strip()
                        if txt:
                            bullets.append(txt)

                    if title:
                        results.append({
                            "title":         title,
                            "price":         price,
                            "rating":        rating,
                            "bullet_points": bullets,
                        })
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"  [Amazon/Playwright] Page error: {e}")
        finally:
            await browser.close()

    logger.info(f"  [Amazon/Playwright] Scraped {len(results)} products")
    return results


async def _playwright_scrape_tiktok(product_name: str, logger) -> dict:
    """
    Scrape TikTok search results using Playwright headless Chromium.
    TikTok is fully JS-rendered — this is the only way to get real data.
    Returns dict with video_cards list and top hashtag/view data.
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright not installed. Run: "
            "pip install playwright==1.44.0 --break-system-packages && playwright install chromium"
        )

    result = {
        "query":       product_name,
        "video_cards": [],
        "hashtags":    [],
        "scraped_at":  datetime.now().isoformat(),
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=SCRAPE_HEADERS["User-Agent"],
            locale="en-US",
            viewport={"width": 1440, "height": 900},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = await ctx.new_page()

        try:
            query = requests.utils.quote(product_name)
            url   = f"https://www.tiktok.com/search?q={query}"
            logger.info(f"  [TikTok/Playwright] Loading: {url}")
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)  # let React hydrate

            # Scroll to load more results
            for _ in range(3):
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(1.5)

            # Grab video cards — TikTok search results
            cards = await page.query_selector_all('[data-e2e="search_video-item"]')
            if not cards:
                # Fallback selector patterns TikTok has used
                cards = await page.query_selector_all(
                    'div[class*="DivItemContainer"], div[class*="video-feed-item"]'
                )
            logger.info(f"  [TikTok/Playwright] Found {len(cards)} video cards")

            for card in cards[:12]:
                try:
                    desc_el   = await card.query_selector('[data-e2e="search-card-desc"], [class*="SpanText"]')
                    author_el = await card.query_selector('[data-e2e="search-card-user-unique-id"], [class*="AuthorTitle"]')
                    likes_el  = await card.query_selector('[data-e2e="search-card-like-count"], [class*="StrongText"]')

                    desc   = (await desc_el.inner_text()).strip()   if desc_el   else ""
                    author = (await author_el.inner_text()).strip()  if author_el else ""
                    likes  = (await likes_el.inner_text()).strip()   if likes_el  else ""

                    if desc or author:
                        result["video_cards"].append({
                            "description": desc,
                            "author":      author,
                            "likes":       likes,
                        })
                except Exception:
                    continue

            # Grab hashtag suggestions from the search bar or related area
            hashtag_els = await page.query_selector_all(
                'a[href*="/tag/"], [class*="HashtagName"], span[class*="tag"]'
            )
            for h in hashtag_els[:15]:
                txt = (await h.inner_text()).strip()
                if txt and txt.startswith("#"):
                    result["hashtags"].append(txt)

        except Exception as e:
            logger.error(f"  [TikTok/Playwright] Page error: {e}")
        finally:
            await browser.close()

    logger.info(f"  [TikTok/Playwright] {len(result['video_cards'])} videos, {len(result['hashtags'])} hashtags")
    return result


# =========================================================================
# STEP A — Pull from Zendrop (live API)
# =========================================================================

def step_a_zendrop(product_name: str, product_id: str, slug: str, logger) -> dict:
    logger.info("=== Step A: Fetching Zendrop data ===")

    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed — run: pip install requests --break-system-packages")

    zd_headers = {
        "Authorization": f"Bearer {ZENDROP_API_KEY}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    raw_data = {}

    # 1. Fetch by product ID (fastest)
    if product_id:
        try:
            resp = requests.get(f"{ZENDROP_BASE}/products/{product_id}", headers=zd_headers, timeout=20)
            if resp.status_code == 200:
                raw_data = resp.json()
                logger.info(f"  Zendrop: fetched by ID {product_id}")
            else:
                logger.warning(f"  Zendrop fetch-by-ID: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"  Zendrop fetch-by-ID error: {e}")

    # 2. Search by name
    if not raw_data:
        try:
            resp = requests.get(
                f"{ZENDROP_BASE}/products/search",
                headers=zd_headers,
                params={"query": product_name, "limit": 5},
                timeout=20,
            )
            if resp.status_code == 200:
                data  = resp.json()
                items = data.get("products") or data.get("data") or data.get("results") or []
                if items:
                    raw_data = items[0]
                    logger.info(f"  Zendrop: found by search — ID {raw_data.get('id', '?')}")
                else:
                    logger.warning(f"  Zendrop search returned 0 results for: {product_name}")
            else:
                logger.warning(f"  Zendrop search: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"  Zendrop search error: {e}")

    # 3. Catalog keyword match
    if not raw_data:
        try:
            resp = requests.get(
                f"{ZENDROP_BASE}/products",
                headers=zd_headers,
                params={"limit": 50, "page": 1},
                timeout=20,
            )
            if resp.status_code == 200:
                items    = resp.json().get("products") or resp.json().get("data") or []
                keywords = product_name.lower().split()[:4]
                for p in items:
                    pname = (p.get("name") or p.get("title") or "").lower()
                    if any(kw in pname for kw in keywords):
                        raw_data = p
                        logger.info(f"  Zendrop: catalog match — ID {p.get('id', '?')}")
                        break
                if not raw_data:
                    logger.warning(f"  Zendrop: no catalog match for '{product_name}' in {len(items)} products")
            else:
                logger.warning(f"  Zendrop catalog: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"  Zendrop catalog scan error: {e}")

    if not raw_data:
        # Hard failure — log clearly, do NOT silently stub
        logger.error(
            f"  [ZENDROP NOT FOUND] Could not locate '{product_name}' (ID: {product_id}) "
            f"in Zendrop. Step A will write an empty record. "
            f"Manually verify the product exists at https://app.zendrop.com/products"
        )
        raw_data = {
            "__zendrop_not_found__": True,
            "product_name": product_name,
            "product_id":   product_id,
            "error":        "Product not found in Zendrop via ID, search, or catalog scan",
            "images":       [],
            "variants":     [],
        }

    (get_product_dir(slug) / "zendrop_raw.json").write_text(json.dumps(raw_data, indent=2))
    logger.info("  Zendrop data saved -> zendrop_raw.json")
    return raw_data


# =========================================================================
# STEP B — Scrape internet collateral (all live, no stubs)
# =========================================================================

def step_b_internet_scrape(product_name: str, slug: str, logger) -> dict:
    logger.info("=== Step B: Scraping internet collateral ===")

    if not HAS_REQUESTS:
        raise RuntimeError("requests not installed")

    collateral = {
        "amazon":          [],
        "google_shopping": [],
        "youtube":         [],
        "reddit":          [],
        "tiktok":          {},
        "scraped_at":      datetime.now().isoformat(),
        "errors":          [],
    }

    # -- Amazon via Playwright -------------------------------------------
    try:
        logger.info("  [Amazon] Launching Playwright scraper...")
        collateral["amazon"] = asyncio.run(_playwright_scrape_amazon(product_name, logger))
    except RuntimeError as e:
        # Playwright not installed — this is a real error, log it clearly
        msg = f"[Amazon] FAILED — Playwright not available: {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)
    except Exception as e:
        msg = f"[Amazon] FAILED — {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)

    # -- Google Shopping via DuckDuckGo HTML (working in existing engine) --
    try:
        logger.info("  [Google Shopping] Scraping via DuckDuckGo...")
        q    = requests.utils.quote(product_name + " buy price review shipping")
        resp = requests.get(
            f"https://html.duckduckgo.com/html/?q={q}",
            headers=SCRAPE_HEADERS, timeout=15
        )
        soup  = BeautifulSoup(resp.text, "html.parser")
        items = []
        for r in soup.select(".result")[:12]:
            title_el   = r.select_one(".result__title")
            snippet_el = r.select_one(".result__snippet")
            url_el     = r.select_one(".result__url")
            if title_el:
                items.append({
                    "title":   title_el.get_text(strip=True),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    "url":     url_el.get_text(strip=True)     if url_el     else "",
                })
        collateral["google_shopping"] = items
        logger.info(f"  [Google Shopping] {len(items)} results")
        time.sleep(1.5)
    except Exception as e:
        msg = f"[Google Shopping] FAILED — {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)

    # -- YouTube Data API v3 (OAuth2, same token as social_poster.py) ------
    try:
        logger.info("  [YouTube] Calling Data API v3...")
        access_token = _get_youtube_access_token(logger)
        if not access_token:
            raise ValueError(
                "Could not get YouTube access token. "
                "Verify YouTube Data API v3 is enabled at: "
                "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
            )
        yt_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part":       "snippet",
                "q":          product_name,
                "type":       "video",
                "maxResults": 10,
                "order":      "viewCount",
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if yt_resp.status_code == 200:
            items = yt_resp.json().get("items", [])
            collateral["youtube"] = [
                {
                    "title":       it["snippet"]["title"],
                    "description": it["snippet"].get("description", "")[:500],
                    "channel":     it["snippet"]["channelTitle"],
                    "published":   it["snippet"]["publishedAt"],
                    "video_id":    it["id"].get("videoId", ""),
                }
                for it in items
            ]
            logger.info(f"  [YouTube] {len(items)} videos")
        else:
            raise ValueError(f"YouTube API {yt_resp.status_code}: {yt_resp.text[:300]}")
        time.sleep(1)
    except Exception as e:
        msg = f"[YouTube] FAILED — {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)

    # -- Reddit public JSON API (no auth, works reliably) ------------------
    try:
        logger.info("  [Reddit] Fetching public posts...")
        reddit_resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": product_name, "sort": "relevance", "limit": 15, "t": "year"},
            headers={**SCRAPE_HEADERS, "Accept": "application/json"},
            timeout=15,
        )
        if reddit_resp.status_code == 200:
            posts = reddit_resp.json().get("data", {}).get("children", [])
            collateral["reddit"] = [
                {
                    "title":        p["data"].get("title", ""),
                    "subreddit":    p["data"].get("subreddit", ""),
                    "score":        p["data"].get("score", 0),
                    "selftext":     p["data"].get("selftext", "")[:600],
                    "url":          p["data"].get("url", ""),
                    "num_comments": p["data"].get("num_comments", 0),
                }
                for p in posts
            ]
            logger.info(f"  [Reddit] {len(posts)} posts")
        else:
            raise ValueError(f"Reddit API {reddit_resp.status_code}")
        time.sleep(1)
    except Exception as e:
        msg = f"[Reddit] FAILED — {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)

    # -- TikTok via Playwright (JS-rendered, no other option) --------------
    try:
        logger.info("  [TikTok] Launching Playwright scraper...")
        collateral["tiktok"] = asyncio.run(_playwright_scrape_tiktok(product_name, logger))
    except RuntimeError as e:
        msg = f"[TikTok] FAILED — Playwright not available: {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)
    except Exception as e:
        msg = f"[TikTok] FAILED — {e}"
        logger.error(f"  {msg}")
        collateral["errors"].append(msg)

    # Log any sources that failed
    if collateral["errors"]:
        logger.warning(f"  Step B completed with {len(collateral['errors'])} source errors (see above)")
    else:
        logger.info("  Step B: all sources scraped successfully")

    (get_product_dir(slug) / "internet_raw.json").write_text(
        json.dumps(collateral, indent=2, ensure_ascii=False)
    )
    logger.info("  Internet collateral saved -> internet_raw.json")
    return collateral


# =========================================================================
# STEP C — Feed through Quinn (Hormozi × Gary Vee × Kamil Sattar)
# =========================================================================

QUINN_SYSTEM_PROMPT = """You are a world-class direct response copywriter and ecom content strategist.
You have internalized the frameworks of:

1. ALEX HORMOZI (Grand Slam Offers, Value Equation, direct response copy)
   - Value Equation: Dream Outcome × Perceived Likelihood / (Time Delay × Effort & Sacrifice)
   - Every headline must maximize Dream Outcome and Perceived Likelihood while minimizing Time Delay and Effort
   - Hook formula: [Relatable Identity] + [Specific Outcome] + [Unusual Method/Time Frame]
   - Copy sequence: Pain → Agitate → Dream Outcome → Vehicle → Offer → Urgency
   - Ad structure: Hook 0-3s | Problem 3-8s | Agitate 8-13s | Solution 13-18s | Offer 18-23s | CTA 23-26s

2. GARY VEE (platform-native content, jab-jab-jab-right-hook, repurposing pyramid)
   - Jab = give value, entertain, educate (no ask)
   - Right Hook = clear offer with CTA
   - Ratio: 3 jabs for every 1 right hook
   - TikTok: raw, authentic, trend-native, fast cuts, no polish
   - Instagram: slightly more produced, carousel-friendly, lifestyle context
   - YouTube: longer attention, searchable titles, chapters, strong CTAs
   - 1 pillar piece generates 30+ micro-content pieces

3. KAMIL SATTAR / THE ECOM KING (TikTok organic dropshipping, POD formula, UGC scripts)
   - POD structure: Problem (0-5s) → Outcome (5-10s) → Demo (10-25s) → CTA (25-30s)
   - Optimal posting times: 7am, 12pm, 8pm Central Time
   - Hook formulas: "POV:", "This [product] does...", "Why everyone is buying...", "I tested..."
   - 3-video 3-day product test before scaling
   - UGC-style: first person, casual, no brand feel
   - Comment bait: always end with an open question or bold claim that invites disagreement

Write copy that sells without sounding like an ad. Every word earns its place."""


def _load_advisors(logger) -> dict:
    """Load all three advisor JSON reference files."""
    advisors = {}
    advisors_dir = Path(__file__).parent / "advisors"
    for name in ["hormozi", "garyvee", "kamil"]:
        path = advisors_dir / f"{name}.json"
        try:
            advisors[name] = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"  Loaded advisor: {name}.json")
        except Exception as e:
            logger.warning(f"  Could not load {name}.json: {e}")
            advisors[name] = {}
    return advisors


def step_c_quinn(
    product_name: str,
    zendrop_data: dict,
    internet_data: dict,
    slug: str,
    logger,
) -> dict:
    logger.info("=== Step C: Generating marketing copy (Hormozi × Gary Vee × Kamil) ===")

    advisors = _load_advisors(logger)

    amazon_titles  = [a.get("title", "")   for a in (internet_data.get("amazon") or [])[:5]]
    amazon_bullets = []
    for a in (internet_data.get("amazon") or [])[:3]:
        amazon_bullets.extend(a.get("bullet_points", []))

    reddit_titles = [r.get("title", "")   for r in (internet_data.get("reddit") or [])[:6]]
    yt_titles     = [v.get("title", "")   for v in (internet_data.get("youtube") or [])[:6]]
    goog_snippets = [g.get("snippet", "") for g in (internet_data.get("google_shopping") or [])[:5]]
    tiktok_descs  = [v.get("description", "") for v in (internet_data.get("tiktok", {}).get("video_cards") or [])[:5]]
    tiktok_tags   = internet_data.get("tiktok", {}).get("hashtags", [])[:10]

    zd_desc  = (zendrop_data.get("description") or zendrop_data.get("product_description")
                or zendrop_data.get("name") or product_name)
    zd_price = (zendrop_data.get("price") or zendrop_data.get("cost")
                or zendrop_data.get("wholesale_price") or "N/A")
    zd_sku   = zendrop_data.get("sku") or zendrop_data.get("supplier_sku") or "N/A"

    # Distill key advisor hook formulas into the prompt
    hormozi_hooks = (advisors.get("hormozi", {}).get("hook_formulas", []) or [])[:4]
    kamil_hooks   = (advisors.get("kamil", {}).get("hook_formulas_for_ecom", []) or [])[:4]
    gv_jab_types  = (advisors.get("garyvee", {}).get("jab_jab_jab_right_hook", {}).get("jab_types", []) or [])[:3]

    filled_prompt = f"""Product: {product_name}
Wholesale price: {zd_price} | SKU: {zd_sku}

SUPPLIER DESCRIPTION:
{str(zd_desc)[:800]}

LIVE MARKET INTEL:
Amazon competitor titles: {amazon_titles}
Amazon bullet points: {amazon_bullets[:10]}
Google Shopping snippets: {goog_snippets}
Reddit community pain points: {reddit_titles}
YouTube top video titles: {yt_titles}
TikTok trending descriptions: {tiktok_descs}
TikTok trending hashtags: {tiktok_tags}

HORMOZI HOOK FORMULAS TO CHOOSE FROM: {hormozi_hooks}
KAMIL HOOK FORMULAS TO CHOOSE FROM: {kamil_hooks}
GARY VEE JAB CONTENT TYPES: {gv_jab_types}

Generate ORIGINAL copy — never copy competitor phrasing. US consumers 18-35.
Use the frameworks above. Be punchy, benefit-first, conversational.

Return ONLY valid JSON — no markdown fences, no commentary, pure JSON:
{{
  "offer_headline": "Hormozi Value Equation headline under 80 chars — Dream Outcome + fast + easy",
  "benefit_bullets": [
    "Outcome-first bullet — lead with the result, not the feature",
    "Second biggest benefit — bold claim, specific number if possible",
    "Objection-crusher — preemptively handles top hesitation",
    "Social proof angle — reviews, users, results",
    "Risk-reversal — guarantee, free shipping, easy returns"
  ],
  "tiktok_scripts": [
    {{
      "angle": "problem_focus",
      "framework": "Kamil POD + Hormozi agitate",
      "hook": "0-3s scroll-stopping hook using Kamil formula",
      "problem": "3-8s relatable pain — make them feel it",
      "agitate": "8-13s twist the knife — why it keeps happening",
      "solution": "13-20s product reveal + single biggest outcome",
      "social_proof": "20-25s bold stat, transformation, or UGC claim",
      "cta": "25-30s urgent CTA — link in bio + open loop",
      "comment_bait": "Bold statement or question that invites disagreement"
    }},
    {{
      "angle": "demo_focus",
      "framework": "Kamil satisfying demo",
      "hook": "Hook that teases the visual payoff",
      "problem": "Quick setup of the problem",
      "agitate": "Why other solutions fail",
      "solution": "Step-by-step demo — describe visually",
      "social_proof": "Result people can see or feel",
      "cta": "CTA with urgency trigger",
      "comment_bait": "Question about their current solution"
    }},
    {{
      "angle": "social_proof_focus",
      "framework": "Gary Vee right hook — offer with proof",
      "hook": "Social proof hook — numbers or transformation",
      "problem": "Identify who this is for",
      "agitate": "Cost of NOT having this",
      "solution": "Product + offer stack",
      "social_proof": "Reviews, orders, results",
      "cta": "Hard CTA — discount, urgency, link",
      "comment_bait": "Tag someone who needs this"
    }}
  ],
  "instagram_captions": [
    {{
      "type": "jab_educational",
      "framework": "Gary Vee jab — teach something",
      "caption": "Value-first caption. Teach. No hard sell. Soft CTA at end.",
      "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"]
    }},
    {{
      "type": "jab_entertainment",
      "framework": "Gary Vee jab — entertain",
      "caption": "Entertaining, relatable, lifestyle caption. No pitch.",
      "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"]
    }},
    {{
      "type": "right_hook_offer",
      "framework": "Gary Vee right hook — Hormozi offer",
      "caption": "Full Hormozi offer caption. Grand Slam structure. Hard CTA. Link in bio.",
      "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"]
    }}
  ],
  "youtube_descriptions": [
    {{
      "type": "shorts_demo",
      "framework": "Gary Vee repurposing — demo short",
      "hook": "Searchable title-hook for the Short",
      "body": "Demo script — describe visually, benefit-focused, 45s max",
      "cta": "Subscribe + link in description",
      "hashtags": ["#Shorts","#tag2","#tag3"]
    }},
    {{
      "type": "shorts_review",
      "framework": "Gary Vee repurposing — UGC-style review",
      "hook": "Honest review hook — builds trust",
      "body": "First-person review script — authentic, Kamil UGC style",
      "cta": "Link in description to grab yours",
      "hashtags": ["#Shorts","#tag2","#tag3"]
    }}
  ],
  "store_description": "150-200 word store page description. Benefit-first. Hormozi risk-reversal close. End with guarantee + shipping promise.",
  "ad_hooks": [
    "Hook variant 1 — Kamil POV formula",
    "Hook variant 2 — Hormozi identity call-out",
    "Hook variant 3 — curiosity gap",
    "Hook variant 4 — bold claim/stat",
    "Hook variant 5 — problem statement"
  ],
  "hashtags": {{
    "tiktok": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8","#tag9","#tag10"],
    "instagram": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8"],
    "youtube": ["#Shorts","#tag2","#tag3","#tag4","#tag5"]
  }},
  "comment_bait": "One bold statement or question for the comment section"
}}"""

    quinn_output = None

    # ── Try Quinn on port 8765 ────────────────────────────────────────────
    if HAS_REQUESTS:
        for endpoint in ["/api/chat", "/chat", "/v1/chat"]:
            try:
                resp = requests.post(
                    f"{QUINN_BASE}{endpoint}",
                    json={
                        "system":   QUINN_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": filled_prompt}],
                    },
                    timeout=120,
                )
                if resp.status_code == 200:
                    data   = resp.json()
                    reply  = data.get("content") or data.get("reply") or data.get("message") or ""
                    parsed = _extract_json(reply)
                    if parsed:
                        quinn_output = parsed
                        logger.info(f"  Quinn: copy generated via {QUINN_BASE}{endpoint}")
                        break
                    else:
                        logger.warning(f"  Quinn {endpoint}: 200 OK but no valid JSON")
            except requests.exceptions.ConnectionError:
                logger.warning(f"  Quinn {endpoint}: connection refused")
            except Exception as e:
                logger.warning(f"  Quinn {endpoint}: {e}")

    # ── Fallback: Ollama ──────────────────────────────────────────────────
    if not quinn_output and HAS_REQUESTS:
        try:
            logger.info(f"  Quinn offline — trying Ollama ({OLLAMA_MODEL})...")
            combined = QUINN_SYSTEM_PROMPT + "\n\n" + filled_prompt
            resp = requests.post(
                f"{OLLAMA_BASE}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": combined, "stream": False},
                timeout=180,
            )
            if resp.status_code == 200:
                raw    = resp.json().get("response", "")
                parsed = _extract_json(raw)
                if parsed:
                    quinn_output = parsed
                    logger.info("  Ollama: copy generated")
                else:
                    logger.error("  Ollama: no valid JSON in response")
            else:
                logger.error(f"  Ollama: {resp.status_code} {resp.text[:200]}")
        except requests.exceptions.ConnectionError:
            logger.error("  Ollama: connection refused")
        except Exception as e:
            logger.error(f"  Ollama: {e}")

    if not quinn_output:
        raise RuntimeError(
            "Step C FAILED: Both Quinn (port 8765) and Ollama (port 11434) are offline "
            "or returned invalid JSON. Start Quinn or run: ollama serve"
        )

    (get_product_dir(slug) / "quinn_copy.json").write_text(
        json.dumps(quinn_output, indent=2, ensure_ascii=False)
    )
    logger.info("  Quinn copy saved -> quinn_copy.json")

    # ── Auto-trigger content calendar builder ─────────────────────────────
    try:
        try:
            from agents.content_calendar_builder import build_content_calendar
        except ImportError:
            import importlib.util, pathlib
            _cal_path = pathlib.Path(__file__).parent / "content_calendar_builder.py"
            _spec = importlib.util.spec_from_file_location("content_calendar_builder", _cal_path)
            _mod  = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            build_content_calendar = _mod.build_content_calendar

        logger.info("  Building content calendar (30 days × 3 frameworks)...")
        build_content_calendar(product_name, slug, quinn_output, logger)
        logger.info("  Content calendar saved -> content_calendar.json")
    except Exception as e:
        logger.warning(f"  Content calendar builder skipped: {e}")

    return quinn_output


# =========================================================================
# STEP D — Package for Prometheus
# =========================================================================

def step_d_prometheus_manifest(
    product_name: str,
    slug: str,
    zendrop_data: dict,
    quinn_data: dict,
    logger,
) -> dict:
    logger.info("=== Step D: Packaging for Prometheus ===")

    raw_images = (
        zendrop_data.get("images") or zendrop_data.get("product_images") or
        zendrop_data.get("media") or zendrop_data.get("photos") or []
    )
    image_urls = []
    for img in raw_images:
        if isinstance(img, str) and img.startswith("http"):
            image_urls.append(img)
        elif isinstance(img, dict):
            for key in ("url", "src", "image_url", "original", "large", "medium"):
                val = img.get(key, "")
                if val and str(val).startswith("http"):
                    image_urls.append(str(val))
                    break

    # ── Dual-format script: new (tiktok_scripts) or legacy (ad_script_30s) ──
    tiktok_scripts = quinn_data.get("tiktok_scripts", [])
    if tiktok_scripts:
        primary = next(
            (s for s in tiktok_scripts if s.get("angle") == "problem_focus"),
            tiktok_scripts[0]
        )
        script_text = " ".join(filter(None, [
            primary.get("hook", ""),     primary.get("problem", ""),
            primary.get("agitate", ""),  primary.get("solution", ""),
            primary.get("social_proof", ""), primary.get("cta", ""),
        ])).strip()
    else:
        ad = quinn_data.get("ad_script_30s", {})
        script_text = " ".join(filter(None, [
            ad.get("hook", ""), ad.get("problem", ""),
            ad.get("solution", ""), ad.get("proof", ""), ad.get("cta", ""),
        ])).strip()

    # ── Resolved fields: new format → legacy fallback ─────────────────────
    resolved_title       = (quinn_data.get("offer_headline")
                            or quinn_data.get("product_title")
                            or product_name)
    resolved_bullets     = (quinn_data.get("benefit_bullets")
                            or quinn_data.get("bullet_points")
                            or [])
    resolved_description = (quinn_data.get("store_description")
                            or quinn_data.get("long_form_description")
                            or "")
    resolved_hashtags    = (quinn_data.get("hashtags") or [])

    # Synthesise legacy ad_script_30s block if missing (for Prometheus compat)
    legacy_ad_block = quinn_data.get("ad_script_30s") or (
        {
            "hook":     tiktok_scripts[0].get("hook", "")         if tiktok_scripts else "",
            "problem":  tiktok_scripts[0].get("problem", "")      if tiktok_scripts else "",
            "solution": tiktok_scripts[0].get("solution", "")     if tiktok_scripts else "",
            "proof":    tiktok_scripts[0].get("social_proof", "") if tiktok_scripts else "",
            "cta":      tiktok_scripts[0].get("cta", "")          if tiktok_scripts else "",
        }
    )

    manifest = {
        "product_name": product_name,
        "product_slug": slug,
        "created_at":   datetime.now().isoformat(),
        "status":       "ready",
        "prometheus_job": {
            "product":        product_name,
            "niche":          "dropshipping",
            "pillar_script":  script_text,
            "image_urls":     image_urls,
            "platforms":      ["tiktok", "instagram", "youtube", "pinterest", "facebook"],
            "add_music":      True,
            "add_voiceover":  True,
            "tiktok_scripts": tiktok_scripts,
            "ad_hooks":       quinn_data.get("ad_hooks", []),
        },
        "copy": {
            # New format fields
            "offer_headline":     resolved_title,
            "benefit_bullets":    resolved_bullets,
            "store_description":  resolved_description,
            "tiktok_scripts":     tiktok_scripts,
            "instagram_captions": quinn_data.get("instagram_captions", []),
            "youtube_descriptions": quinn_data.get("youtube_descriptions", []),
            "ad_hooks":           quinn_data.get("ad_hooks", []),
            "comment_bait":       quinn_data.get("comment_bait", ""),
            "hashtags":           resolved_hashtags,
            # Legacy fields (kept for Prometheus backward compat)
            "product_title":         resolved_title,
            "bullet_points":         resolved_bullets,
            "long_form_description": resolved_description,
            "ad_script_30s":         legacy_ad_block,
            "full_script_text":      script_text,
        },
        "assets": {
            "zendrop_images": image_urls,
            "image_count":    len(image_urls),
            "collateral_dir": str(get_product_dir(slug)),
        },
        "supplier": {
            "platform":   "Zendrop",
            "product_id": zendrop_data.get("id") or zendrop_data.get("product_id") or "",
            "sku":        zendrop_data.get("sku") or zendrop_data.get("supplier_sku") or "",
            "price":      zendrop_data.get("price") or zendrop_data.get("cost") or "",
            "title":      zendrop_data.get("title") or zendrop_data.get("name") or product_name,
        },
    }

    (get_product_dir(slug) / "prometheus_ready.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    logger.info("  Prometheus manifest saved -> prometheus_ready.json")
    return manifest


# =========================================================================
# MAIN ENTRY POINT
# =========================================================================

def run_onboarding(
    product_name: str,
    product_id:   str | None  = None,
    channel:      str | None  = None,
    score:        float | None = None,
) -> dict:
    slug   = slugify(product_name)
    logger = get_logger(slug)

    logger.info("=" * 60)
    logger.info(f"ONBOARDING STARTED: {product_name}")
    logger.info(f"slug={slug}  zendrop_id={product_id}  channel={channel}  score={score}")
    logger.info("=" * 60)

    result = {
        "product_name": product_name,
        "product_slug": slug,
        "started_at":   datetime.now().isoformat(),
        "steps":        {},
        "status":       "running",
    }

    try:
        zendrop_data  = step_a_zendrop(product_name, product_id, slug, logger)
        result["steps"]["A_zendrop"]             = "done"

        internet_data = step_b_internet_scrape(product_name, slug, logger)
        result["steps"]["B_internet_scrape"]     = "done"
        result["steps"]["B_source_errors"]       = internet_data.get("errors", [])

        quinn_data    = step_c_quinn(product_name, zendrop_data, internet_data, slug, logger)
        result["steps"]["C_quinn_copy"]          = "done"

        manifest      = step_d_prometheus_manifest(product_name, slug, zendrop_data, quinn_data, logger)
        result["steps"]["D_prometheus_manifest"] = "done"

        result.update({
            "status":              "complete",
            "completed_at":        datetime.now().isoformat(),
            "output_dir":          str(get_product_dir(slug)),
            "prometheus_manifest": str(get_product_dir(slug) / "prometheus_ready.json"),
            "copy_preview": {
                "title":           (quinn_data.get("offer_headline")
                                    or quinn_data.get("product_title")
                                    or product_name),
                "bullet_count":    len(quinn_data.get("benefit_bullets")
                                       or quinn_data.get("bullet_points") or []),
                "tiktok_scripts":  len(quinn_data.get("tiktok_scripts", [])),
                "ig_captions":     len(quinn_data.get("instagram_captions", [])),
                "yt_descriptions": len(quinn_data.get("youtube_descriptions", [])),
                "ad_hooks":        len(quinn_data.get("ad_hooks", [])),
                "image_count":     len(manifest["assets"]["zendrop_images"]),
                "script_chars":    len(manifest["prometheus_job"]["pillar_script"]),
            },
        })

        logger.info("=" * 60)
        logger.info(f"ONBOARDING COMPLETE: {product_name}")
        logger.info(f"Output: {get_product_dir(slug)}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Onboarding pipeline FAILED: {e}")
        logger.error(traceback.format_exc())
        result["status"] = "error"
        result["error"]  = str(e)

    (get_product_dir(slug) / "onboarding_result.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    product_arg = sys.argv[1] if len(sys.argv) > 1 else "Self-Cleaning Lint Brush"
    pid_arg     = sys.argv[2] if len(sys.argv) > 2 else None
    out = run_onboarding(product_arg, pid_arg)
    print(json.dumps(out, indent=2))
