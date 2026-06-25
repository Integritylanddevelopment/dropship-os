import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""
pipeline_glue.py -- Full Pipeline Orchestrator
===============================================
Connects: Discovery -> Scoring -> Content Generation -> Social Posting

Usage:
    from engines.pipeline_glue import run_full_pipeline, post_to_platforms

    manifest = run_full_pipeline(query="pet accessories", limit=5)
    post_to_platforms(manifest, platforms=["pinterest"])

Or standalone:
    python engines/pipeline_glue.py --query "pet accessories" --limit 5
    python engines/pipeline_glue.py --query "kitchen gadgets" --limit 3 --post
    python engines/pipeline_glue.py --post-only          # post from existing decisions.json
"""

import os
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests

# ── Environment ──────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path(__file__).parent.parent / ".env.local", override=True)
except ImportError:
    pass

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
)
logger = logging.getLogger("pipeline_glue")

# ── Paths & Constants ────────────────────────────────────────────────────
SHIPSTACK_ROOT = Path(__file__).parent.parent
DECISIONS_PATH = SHIPSTACK_ROOT / "decisions.json"
CARDS_DIR      = SHIPSTACK_ROOT / "pinterest_cards"
PROMETHEUS_DIR = SHIPSTACK_ROOT / "prometheus_output"

ENGINE_URL     = os.getenv("SHIPSTACK_ENGINE_URL", "http://127.0.0.1:8889")
SOCIAL_URL     = os.getenv("SOCIAL_AI_URL", "http://127.0.0.1:8867")
PROMETHEUS_URL = os.getenv("PROMETHEUS_ENGINE_URL", "http://127.0.0.1:8766")

ALL_PLATFORMS  = ["pinterest", "tiktok", "youtube", "instagram"]

REQUEST_TIMEOUT = 30  # seconds


# ── Helpers ──────────────────────────────────────────────────────────────

def _http_post(url: str, payload: dict, label: str = "") -> Optional[dict]:
    """POST JSON to a local service, return parsed response or None on error."""
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        logger.error(f"[{label}] Connection refused: {url} -- is the service running?")
    except requests.Timeout:
        logger.error(f"[{label}] Request timed out: {url}")
    except requests.HTTPError as e:
        logger.error(f"[{label}] HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        logger.error(f"[{label}] Unexpected error: {e}")
    return None


def _http_get(url: str, label: str = "") -> Optional[dict]:
    """GET from a local service, return parsed response or None on error."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[{label}] GET failed {url}: {e}")
    return None


def get_decisions_path() -> Path:
    """Return the path to decisions.json."""
    return DECISIONS_PATH


# ── Step 1: Discovery ───────────────────────────────────────────────────

def _run_discovery(query: Optional[str] = None) -> List[dict]:
    """
    Call the discovery pipeline via HTTP.
    Returns a list of report dicts from /api/discover, or tries /api/recommend
    as a fallback (which includes scoring).
    """
    logger.info(f"[DISCOVER] Starting discovery (query={query!r})")

    payload = {}
    if query:
        payload["query"] = query

    # Try /api/discover first
    result = _http_post(f"{ENGINE_URL}/api/discover", payload, "DISCOVER")
    if result and result.get("reports"):
        reports = result["reports"]
        logger.info(f"[DISCOVER] Got {len(reports)} reports from discovery pipeline")
        return reports

    # If discovery returned nothing, try /api/research as fallback
    if query:
        logger.info("[DISCOVER] No discovery reports, trying /api/research fallback")
        research = _http_post(
            f"{ENGINE_URL}/api/research",
            {"query": query, "limit": 20},
            "RESEARCH",
        )
        if research and research.get("products"):
            logger.info(f"[DISCOVER] Got {len(research['products'])} products from research")
            return research["products"]

    logger.warning("[DISCOVER] No products found from any source")
    return []


# ── Step 2: Scoring ─────────────────────────────────────────────────────

def _score_products(reports: List[dict], limit: int = 5) -> List[dict]:
    """
    Score products through DecisionEngine via /api/decide.
    Returns top-N ranked decisions with product data attached.
    """
    logger.info(f"[SCORE] Scoring {len(reports)} products, keeping top {limit}")

    # Convert reports into product dicts that /api/decide expects
    products = []
    for i, rpt in enumerate(reports):
        products.append({
            "id": rpt.get("keyword", rpt.get("id", f"p_{i}")),
            "title": rpt.get("keyword", rpt.get("title", f"Product {i}")),
            "price": float(rpt.get("avg_price", rpt.get("price", 5.0))),
            "supplier": rpt.get("top_supplier", rpt.get("supplier", "mixed")),
            "reviews": int(rpt.get("signal_count", rpt.get("reviews", 0))),
            "rating": float(rpt.get("avg_rating", rpt.get("rating", 4.0))),
            "niche": rpt.get("keyword", rpt.get("niche", "general")),
            "description": rpt.get("summary", rpt.get("description", "")),
        })

    if not products:
        return []

    # Try /api/recommend first (it does discover+score in one call)
    # But if we already have products, use /api/decide directly
    result = _http_post(
        f"{ENGINE_URL}/api/decide",
        {"products": products},
        "SCORE",
    )

    if not result or "rankings" not in result:
        logger.warning("[SCORE] Scoring failed, returning products unsorted")
        # Fallback: return products as-is with synthetic scores
        scored = []
        for p in products[:limit]:
            scored.append({
                "product_id": p["id"],
                "title": p["title"],
                "price": p["price"],
                "niche": p["niche"],
                "description": p["description"],
                "score": 0.5,
                "margin_potential": 0.50,
                "competition_level": "unknown",
                "trend_signal": "steady",
                "channels": ["pinterest"],
                "rationale": "Scoring unavailable -- default values",
            })
        return scored

    rankings = result["rankings"][:limit]

    # Attach product metadata to each ranking (decisions only have product_id)
    product_map = {p["id"]: p for p in products}
    enriched = []
    for rank in rankings:
        pid = rank.get("product_id", "")
        prod = product_map.get(pid, {})
        enriched.append({
            **rank,
            "title": prod.get("title", pid),
            "price": prod.get("price", 0),
            "niche": prod.get("niche", "general"),
            "description": prod.get("description", ""),
        })

    logger.info(f"[SCORE] Top {len(enriched)} products scored")
    return enriched


# ── Step 3: Write decisions.json ─────────────────────────────────────────

def _write_decisions(scored_products: List[dict]) -> Path:
    """
    Write scored products to decisions.json in the format that
    pinterest_poster --auto expects.

    Format:
    {
        "generated_at": "2026-06-25T12:00:00Z",
        "count": 5,
        "products": [
            {
                "product_id": "pet_collar",
                "title": "Pet Collar",
                "niche": "pet accessories",
                "score": 0.85,
                "margin_potential": 0.50,
                "competition_level": "low",
                "trend_signal": "hot",
                "channels": ["pinterest", "tiktok"],
                "description": "...",
                "rationale": "..."
            }
        ]
    }
    """
    decisions = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(scored_products),
        "products": scored_products,
    }

    DECISIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2, ensure_ascii=False)

    logger.info(f"[DECISIONS] Wrote {len(scored_products)} products to {DECISIONS_PATH}")
    return DECISIONS_PATH


# ── Step 4: Generate content (cards + videos) ───────────────────────────

def _generate_cards(scored_products: List[dict]) -> List[dict]:
    """
    Generate Pinterest product card images for each scored product.
    Returns list of {product_id, card_path} dicts.
    """
    logger.info(f"[CARDS] Generating {len(scored_products)} product cards")

    # Import generate_product_card locally to avoid hard dependency
    try:
        sys.path.insert(0, str(SHIPSTACK_ROOT))
        from social_ai_agent.pinterest_poster import generate_product_card
    except ImportError as e:
        logger.warning(f"[CARDS] Cannot import pinterest_poster: {e}")
        logger.warning("[CARDS] Skipping card generation")
        return []

    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    cards = []

    for prod in scored_products:
        product_name = prod.get("title", prod.get("product_id", "unknown"))
        niche = prod.get("niche", "general")
        margin = prod.get("margin_potential", 0.50) * 100  # convert to percentage
        score = prod.get("score", 0.5) * 100  # convert to 0-100 scale

        safe_name = product_name.replace(" ", "_")[:30].lower()
        output_path = str(CARDS_DIR / f"{safe_name}_card.png")

        try:
            result = generate_product_card(
                product=product_name,
                niche=niche,
                margin=margin,
                score=score,
                output_path=output_path,
            )
            if result:
                cards.append({
                    "product_id": prod.get("product_id", safe_name),
                    "card_path": result,
                })
                logger.info(f"  [CARD] {product_name} -> {Path(result).name}")
            else:
                logger.warning(f"  [CARD] Failed for {product_name}")
        except Exception as e:
            logger.error(f"  [CARD] Error generating card for {product_name}: {e}")

    logger.info(f"[CARDS] Generated {len(cards)}/{len(scored_products)} cards")
    return cards


def _find_videos() -> List[dict]:
    """
    Scan prometheus_output/ for existing product videos.
    Returns list of {filename, path, product_id} dicts.
    """
    videos = []
    if not PROMETHEUS_DIR.exists():
        logger.info("[VIDEOS] No prometheus_output/ directory found")
        return videos

    for ext in ("*.mp4", "*.webm", "*.mov"):
        for vpath in PROMETHEUS_DIR.glob(ext):
            videos.append({
                "filename": vpath.name,
                "path": str(vpath),
                "product_id": vpath.stem,
            })

    logger.info(f"[VIDEOS] Found {len(videos)} videos in prometheus_output/")
    return videos


# ── Main Pipeline ────────────────────────────────────────────────────────

def run_full_pipeline(
    query: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Orchestrate the complete pipeline:
        Discovery -> Scoring -> decisions.json -> Card Generation

    Args:
        query:  Search term for discovery (None = trending/default)
        limit:  Max number of top products to process

    Returns:
        Manifest dict:
        {
            "products": [...],     # scored product dicts
            "cards": [...],        # {product_id, card_path} dicts
            "videos": [...],       # {filename, path, product_id} dicts
            "decisions_path": str, # path to decisions.json
            "generated_at": str,
            "status": "ok" | "partial" | "empty",
            "errors": [...]
        }
    """
    start = time.time()
    errors = []

    logger.info("=" * 60)
    logger.info(f"[PIPELINE] Starting full pipeline (query={query!r}, limit={limit})")
    logger.info("=" * 60)

    # Step 1: Discover products
    reports = _run_discovery(query)
    if not reports:
        logger.warning("[PIPELINE] Discovery returned no products")
        # If discovery pipeline is down, try /api/recommend directly
        logger.info("[PIPELINE] Attempting /api/recommend as combined fallback")
        payload = {"limit": limit}
        if query:
            payload["query"] = query
        rec_result = _http_post(f"{ENGINE_URL}/api/recommend", payload, "RECOMMEND")
        if rec_result and rec_result.get("recommendations"):
            scored = rec_result["recommendations"]
            # Enrich with title from product_id
            for s in scored:
                if "title" not in s:
                    s["title"] = s.get("product_id", "Unknown").replace("_", " ").title()
                if "niche" not in s:
                    s["niche"] = s.get("product_id", "general")
                if "channels" not in s:
                    score_val = s.get("score", 0.5)
                    if score_val >= 0.75:
                        s["channels"] = ["tiktok", "instagram", "pinterest"]
                    elif score_val >= 0.50:
                        s["channels"] = ["pinterest", "instagram"]
                    else:
                        s["channels"] = ["pinterest"]
            scored = scored[:limit]
        else:
            errors.append("Discovery and recommend both returned no products")
            return {
                "products": [],
                "cards": [],
                "videos": [],
                "decisions_path": str(DECISIONS_PATH),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "elapsed_sec": round(time.time() - start, 2),
                "status": "empty",
                "errors": errors,
            }
    else:
        # Step 2: Score products
        scored = _score_products(reports, limit)

    if not scored:
        errors.append("Scoring returned no products")
        return {
            "products": [],
            "cards": [],
            "videos": [],
            "decisions_path": str(DECISIONS_PATH),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "elapsed_sec": round(time.time() - start, 2),
            "status": "empty",
            "errors": errors,
        }

    # Step 3: Write decisions.json
    try:
        _write_decisions(scored)
    except Exception as e:
        errors.append(f"Failed to write decisions.json: {e}")
        logger.error(f"[PIPELINE] decisions.json write error: {e}")

    # Step 4: Generate product cards
    cards = _generate_cards(scored)
    if not cards and scored:
        errors.append("Card generation produced no cards (Pillow may not be installed)")

    # Step 5: Collect any existing Prometheus videos
    videos = _find_videos()

    elapsed = round(time.time() - start, 2)
    status = "ok" if cards else ("partial" if scored else "empty")

    manifest = {
        "products": scored,
        "cards": cards,
        "videos": videos,
        "decisions_path": str(DECISIONS_PATH),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "elapsed_sec": elapsed,
        "status": status,
        "errors": errors,
    }

    logger.info("=" * 60)
    logger.info(f"[PIPELINE] Complete in {elapsed}s")
    logger.info(f"  Products: {len(scored)}")
    logger.info(f"  Cards:    {len(cards)}")
    logger.info(f"  Videos:   {len(videos)}")
    logger.info(f"  Status:   {status}")
    if errors:
        logger.warning(f"  Errors:   {errors}")
    logger.info("=" * 60)

    return manifest


# ── Posting ──────────────────────────────────────────────────────────────

def post_to_platforms(
    manifest: Dict[str, Any],
    platforms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Post content from a pipeline manifest to social platforms via
    the Social AI Agent service at :8867.

    Args:
        manifest:   Output from run_full_pipeline()
        platforms:  List of platform names, or None for all configured

    Returns:
        {
            "posted": [{"platform": ..., "product_id": ..., "status": ..., "id": ...}],
            "failed": [{"platform": ..., "product_id": ..., "error": ...}],
            "skipped": [{"platform": ..., "reason": ...}]
        }
    """
    if platforms is None:
        platforms = ALL_PLATFORMS

    products = manifest.get("products", [])
    cards = manifest.get("cards", [])
    videos = manifest.get("videos", [])

    # Build lookup maps
    card_map = {c["product_id"]: c["card_path"] for c in cards}
    video_map = {v["product_id"]: v["path"] for v in videos}

    posted = []
    failed = []
    skipped = []

    logger.info(f"[POST] Posting to platforms: {platforms}")
    logger.info(f"[POST] {len(products)} products, {len(cards)} cards, {len(videos)} videos")

    # Check if Social AI Agent is reachable
    health = _http_get(f"{SOCIAL_URL}/health", "SOCIAL_HEALTH")
    if not health:
        logger.error("[POST] Social AI Agent unreachable at :8867")
        return {
            "posted": [],
            "failed": [{"platform": "all", "error": "Social AI Agent unreachable"}],
            "skipped": [],
        }

    for product in products:
        pid = product.get("product_id", "unknown")
        title = product.get("title", pid)
        niche = product.get("niche", "general")
        score = product.get("score", 0)
        channels = product.get("channels", ["pinterest"])

        for platform in platforms:
            # Skip platforms not recommended for this product's score
            if platform not in channels and platform != "pinterest":
                skipped.append({
                    "platform": platform,
                    "product_id": pid,
                    "reason": f"Score {score:.2f} too low for {platform}",
                })
                continue

            # Build post payload
            post_payload = {
                "platform": platform,
                "product_id": pid,
                "title": title,
                "niche": niche,
                "score": score,
            }

            # Attach card path for image-based platforms
            if platform in ("pinterest", "instagram") and pid in card_map:
                post_payload["image_path"] = card_map[pid]

            # Attach video path for video platforms
            if platform in ("tiktok", "youtube") and pid in video_map:
                post_payload["video_path"] = video_map[pid]
            elif platform in ("tiktok", "youtube") and pid not in video_map:
                skipped.append({
                    "platform": platform,
                    "product_id": pid,
                    "reason": f"No Prometheus video found for {pid}",
                })
                continue

            # Generate content description via social agent
            gen_result = _http_post(
                f"{SOCIAL_URL}/generate",
                {"platform": platform, "topic": f"{title} - {niche} dropshipping product"},
                f"GENERATE/{platform}",
            )
            if gen_result and gen_result.get("draft"):
                post_payload["description"] = gen_result["draft"]

            # Post via social agent
            result = _http_post(
                f"{SOCIAL_URL}/post",
                post_payload,
                f"POST/{platform}",
            )

            if result and result.get("status") in ("queued", "posted", "ok"):
                posted.append({
                    "platform": platform,
                    "product_id": pid,
                    "title": title,
                    "status": result.get("status"),
                    "id": result.get("id", ""),
                })
                logger.info(f"  [POSTED] {title} -> {platform} ({result.get('status')})")
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response"
                failed.append({
                    "platform": platform,
                    "product_id": pid,
                    "title": title,
                    "error": error_msg,
                })
                logger.error(f"  [FAILED] {title} -> {platform}: {error_msg}")

    logger.info(f"[POST] Summary: {len(posted)} posted, {len(failed)} failed, {len(skipped)} skipped")
    return {"posted": posted, "failed": failed, "skipped": skipped}


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ShipStack Pipeline Glue")
    parser.add_argument("--query", "-q", type=str, default=None,
                        help="Search query for discovery")
    parser.add_argument("--limit", "-n", type=int, default=5,
                        help="Max products to process (default: 5)")
    parser.add_argument("--post", action="store_true",
                        help="Also post to social platforms after pipeline")
    parser.add_argument("--post-only", action="store_true",
                        help="Post from existing decisions.json (skip pipeline)")
    parser.add_argument("--platforms", type=str, nargs="+", default=None,
                        help="Platforms to post to (default: all configured)")

    args = parser.parse_args()

    if args.post_only:
        # Load existing manifest from decisions.json
        if not DECISIONS_PATH.exists():
            logger.error(f"No decisions.json found at {DECISIONS_PATH}")
            logger.error("Run the pipeline first: python engines/pipeline_glue.py --query 'pet accessories'")
            sys.exit(1)

        with open(DECISIONS_PATH, "r", encoding="utf-8") as f:
            decisions = json.load(f)

        manifest = {
            "products": decisions.get("products", []),
            "cards": [
                {"product_id": p.get("product_id"), "card_path": str(CARDS_DIR / f"{p.get('product_id', 'x')[:30]}_card.png")}
                for p in decisions.get("products", [])
                if (CARDS_DIR / f"{p.get('product_id', 'x')[:30]}_card.png").exists()
            ],
            "videos": _find_videos(),
        }

        result = post_to_platforms(manifest, args.platforms)
        print(json.dumps(result, indent=2))
        return

    # Run full pipeline
    manifest = run_full_pipeline(query=args.query, limit=args.limit)

    print("\n" + "=" * 50)
    print("PIPELINE MANIFEST")
    print("=" * 50)
    print(f"Status:   {manifest['status']}")
    print(f"Products: {len(manifest['products'])}")
    print(f"Cards:    {len(manifest['cards'])}")
    print(f"Videos:   {len(manifest['videos'])}")
    print(f"Elapsed:  {manifest['elapsed_sec']}s")
    if manifest["errors"]:
        print(f"Errors:   {manifest['errors']}")
    print()

    for i, p in enumerate(manifest["products"], 1):
        print(f"  {i}. {p.get('title', p.get('product_id'))} "
              f"(score={p.get('score', 0):.2f}, "
              f"niche={p.get('niche')}, "
              f"trend={p.get('trend_signal', '?')})")

    # Post if requested
    if args.post:
        print("\n" + "-" * 50)
        print("POSTING TO PLATFORMS")
        print("-" * 50)
        result = post_to_platforms(manifest, args.platforms)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
