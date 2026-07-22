import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""Mission Control pipeline — the one-button full run.

Stages: services -> discover -> pick -> content -> host -> post
Runs in a background thread; UI polls get_status() via the engine's
/api/pipeline/status route. Only one run at a time.
"""
import os
import json
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone

import requests

SHIPSTACK_ROOT = Path(__file__).parent.parent
CARDS_DIR = SHIPSTACK_ROOT / "pinterest_cards"
RUNS_LOG = SHIPSTACK_ROOT / "logs" / "mission_runs.jsonl"
DECISIONS_PATH = SHIPSTACK_ROOT / "decisions.json"

SOCIAL_URL = os.getenv("SOCIAL_AI_URL", "http://127.0.0.1:8867")
PROMETHEUS_URL = os.getenv("PROMETHEUS_ENGINE_URL", "http://127.0.0.1:8766")
LANDING_URL = os.getenv("LANDING_PAGE_URL", "")

def _clean_title(raw: str, max_len: int = 48) -> str:
    """Turn a supplier listing title into a clean retail product name."""
    import re as _re
    if not raw:
        return ""
    t = _re.sub(r"\[.*?\]|\(.*?\)", " ", raw)          # drop bracketed noise
    t = t.split("|")[0].split(",")[0]                   # first clause only
    t = _re.sub(r"\s+", " ", t).strip()
    if t.isupper():
        t = t.title()
    if len(t) > max_len:
        cut = t[:max_len]
        t = cut[:cut.rfind(" ")] if " " in cut else cut
    return t.strip(" -–—·")


STAGE_NAMES = ["services", "discover", "pick", "content", "host", "post"]
STAGE_LABELS = {
    "services": "Check services",
    "discover": "Discover trending products",
    "pick": "Pick winners",
    "content": "Create retail ads",
    "host": "Publish ads + store pages",
    "post": "Post to social media",
}

_LOCK = threading.Lock()


def _new_state():
    return {
        "running": False,
        "run_id": None,
        "started_at": None,
        "finished_at": None,
        "query": None,
        "platforms": [],
        "stages": {n: {"label": STAGE_LABELS[n], "status": "pending", "detail": ""} for n in STAGE_NAMES},
        "log": [],
        "products": [],
        "posts": [],
        "summary": "",
        "error": None,
    }


STATE = _new_state()


def _log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with _LOCK:
        STATE["log"].append(line)
        if len(STATE["log"]) > 200:
            STATE["log"] = STATE["log"][-200:]


def _stage(name: str, status: str, detail: str = ""):
    with _LOCK:
        STATE["stages"][name]["status"] = status
        if detail:
            STATE["stages"][name]["detail"] = detail
    if detail:
        _log(f"{STAGE_LABELS.get(name, name)}: {detail}")


def get_status() -> dict:
    with _LOCK:
        return json.loads(json.dumps(STATE))


def start_run(query: str | None = None, platforms: list | None = None,
              limit: int = 5, dry_run: bool = False) -> dict:
    """Kick off a pipeline run in a background thread. Returns immediately."""
    global STATE
    with _LOCK:
        if STATE["running"]:
            return {"ok": False, "error": "A run is already in progress"}
        STATE = _new_state()
        STATE["running"] = True
        STATE["run_id"] = f"run_{int(time.time())}"
        STATE["started_at"] = datetime.now(timezone.utc).isoformat()
        STATE["query"] = query
        STATE["platforms"] = platforms or ["pinterest"]

    t = threading.Thread(target=_run_pipeline, args=(query, platforms or ["pinterest"], limit, dry_run), daemon=True)
    t.start()
    return {"ok": True, "run_id": STATE["run_id"]}


def _run_pipeline(query, platforms, limit, dry_run):
    try:
        _do_run(query, platforms, limit, dry_run)
    except Exception as e:
        traceback.print_exc()
        with _LOCK:
            STATE["error"] = str(e)
        _log(f"PIPELINE ERROR: {e}")
        # Mark current in-progress stage as error
        with _LOCK:
            for n in STAGE_NAMES:
                if STATE["stages"][n]["status"] == "running":
                    STATE["stages"][n]["status"] = "error"
                    STATE["stages"][n]["detail"] = str(e)[:200]
    finally:
        with _LOCK:
            STATE["running"] = False
            STATE["finished_at"] = datetime.now(timezone.utc).isoformat()
        _save_run()


def _save_run():
    try:
        RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(RUNS_LOG, "a", encoding="utf-8") as f:
            snap = get_status()
            snap.pop("log", None)
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Stages ───────────────────────────────────────────────────────────────

def _do_run(query, platforms, limit, dry_run):
    # STAGE 1: services
    _stage("services", "running")
    svc = {}
    try:
        r = requests.get(f"{SOCIAL_URL}/health", timeout=5)
        svc["social"] = r.ok
    except Exception:
        svc["social"] = False
    try:
        r = requests.get(f"{PROMETHEUS_URL}/health", timeout=5)
        svc["prometheus"] = r.ok
    except Exception:
        svc["prometheus"] = False
    detail = f"social={'up' if svc['social'] else 'DOWN'}, video={'up' if svc['prometheus'] else 'DOWN'}"
    _stage("services", "done", detail)
    if not svc["social"] and not dry_run and platforms:
        _log("WARNING: Social agent down — posting will fail. Continuing anyway.")

    # STAGE 2: discover
    _stage("discover", "running", "collecting signals from Reddit + Google Trends...")
    from discovery_engine import pipeline as dpipe

    kwargs = {"verbose": False, "with_suppliers": False, "max_clusters": 20,
              "fast": True,
              "progress_cb": lambda m: _stage("discover", "running", m)}
    if query:
        q = query if isinstance(query, str) else " ".join(query)
        # Query runs: search ONLY the requested niche (skip generic subreddits)
        # so every signal relates to what Alex asked for.
        kwargs["keywords"] = [q, f"best {q}", f"{q} gadget"]
        kwargs["subreddits"] = []

    result = dpipe.run(**kwargs)
    reports = result.get("reports", [])
    _stage("discover", "done", f"{result.get('total_signals', 0)} signals -> {len(reports)} product opportunities")

    if not reports:
        raise RuntimeError("Discovery found no products — check network access")

    # STAGE 3: pick winners
    _stage("pick", "running")
    from discovery_engine.scoring.clusterer import _is_valid_keyword
    viable = []
    for r in reports:
        if r.get("recommendation") == "reject":
            continue
        titles = [s.get("title") or "" for s in r.get("top_social_sources", [])]
        if not _is_valid_keyword(r.get("product_keyword", ""), titles):
            _log(f"dropped junk keyword: '{r.get('product_keyword')}'")
            continue
        viable.append(r)
    viable.sort(key=lambda r: r["scores"]["overall"], reverse=True)
    # Dedupe: two clusters can produce the same keyword — keep the highest-scoring one
    seen_ids = set()
    uniq = []
    for r in viable:
        pid = r["product_keyword"].replace(" ", "_")[:40]
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        uniq.append(r)
    winners = uniq[:limit]

    if not winners:
        raise RuntimeError("No viable product keywords survived filtering — try a more specific niche")

    products = []
    for w in winners:
        products.append({
            "product_id": w["product_keyword"].replace(" ", "_")[:40],
            "title": w["product_keyword"].title(),
            "keyword": w["product_keyword"],
            "score": w["scores"]["overall"],
            "margin_pct": w.get("margin", {}).get("gross_margin_pct", 0),
            "retail_price": w.get("margin", {}).get("retail_price", 0),
            "recommendation": w.get("recommendation", ""),
            "hooks": w.get("content_hooks", []),
            "intent": list(w.get("buyer_intent_phrases", []))[:5],
            "n_signals": w.get("n_signals", 0),
            "sources": w.get("top_social_sources", [])[:3],
            "card_path": None,
            "card_url": None,
            "photo_url": "",
            "supplier_title": "",
            "supplier_cost": 0.0,
            "compare_at": 0.0,
            "landing_url": "",
            "payment_link": "",
        })
    with _LOCK:
        STATE["products"] = products
    _stage("pick", "done", f"top {len(products)} of {len(viable)} viable products selected")

    # Write decisions.json for compatibility with existing tools
    try:
        with open(DECISIONS_PATH, "w", encoding="utf-8") as f:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                       "count": len(products), "products": products}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log(f"decisions.json write failed: {e}")

    # STAGE 4: retail ads — match a real supplier product, price it, build the ad
    _stage("content", "running", "matching suppliers + building ads...")
    cards_made = 0
    sys.path.insert(0, str(SHIPSTACK_ROOT))
    from social_ai_agent.retail_ad_card import generate_retail_ad
    from discovery_engine.suppliers import cj_dropshipping
    from discovery_engine.scoring import margin_calc

    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(products, 1):
        # 4a. Find a real supplier listing (photo + true cost)
        try:
            _stage("content", "running", f"({i}/{len(products)}) sourcing '{p['keyword']}'...")
            listings = cj_dropshipping.search(p["keyword"], limit=5)
            best = next((l for l in listings if l.get("image") and (l.get("unit_cost") or 0) > 0), None)
            if best:
                p["photo_url"] = best["image"]
                p["supplier_title"] = (best.get("title") or "")[:120]
                p["supplier_cost"] = float(best["unit_cost"])
                # Use the REAL product name on ads/pages, not the generic keyword
                nice = _clean_title(p["supplier_title"])
                if nice:
                    p["title"] = nice
        except Exception as e:
            _log(f"supplier lookup failed for {p['keyword']}: {e}")

        # 4b. Real retail pricing (supplier cost when found, else category estimate)
        cost = p["supplier_cost"] or None
        if cost:
            m = margin_calc.compute(supplier_cost=cost, shipping_cost=4.00)
            p["margin_pct"] = m["gross_margin_pct"]
            raw_retail = m["retail_price"]
        else:
            raw_retail = p.get("retail_price") or 24.99
        retail = float(int(raw_retail)) + 0.99 if raw_retail >= 1 else 9.99
        p["retail_price"] = retail
        p["compare_at"] = float(int(retail * 1.5)) + 0.99

        # 4c. Build the buyer-facing ad card
        try:
            out = str(CARDS_DIR / f"{p['product_id'][:30]}_ad.png")
            quote = p["intent"][0] if p.get("intent") else ""
            res = generate_retail_ad(
                product_name=p["title"],
                photo_url=p["photo_url"],
                retail_price=p["retail_price"],
                compare_at=p["compare_at"],
                hooks=p.get("hooks", []),
                buyer_quote=quote,
                output_path=out,
            )
            if res:
                p["card_path"] = res
                cards_made += 1
                _stage("content", "running", f"({i}/{len(products)}) ad ready: {p['title']}")
        except Exception as e:
            _log(f"ad card failed for {p['title']}: {e}")
    with _LOCK:
        STATE["products"] = products
    with_photos = sum(1 for p in products if p["photo_url"])
    _stage("content", "done", f"{cards_made}/{len(products)} ads built ({with_photos} with real product photos)")

    # STAGE 5: publish — ad images, Stripe payment links, landing pages
    _stage("host", "running")
    hosted = 0
    pages_made = 0
    if dry_run:
        _stage("host", "done", "skipped (dry run)")
    else:
        try:
            from integrations.github_image_host import upload_image
            from integrations import landing_pages as lp
            from social_ai_agent.retail_ad_card import BENEFIT_BY_HOOK, DEFAULT_BENEFIT

            for p in products:
                # 5a. host the ad image
                if p.get("card_path"):
                    try:
                        url = upload_image(p["card_path"], dest_name=f"{p['product_id'][:30]}.png")
                        p["card_url"] = url
                        hosted += 1
                    except Exception as e:
                        _log(f"image host failed for {p['title']}: {e}")

                # 5b. Stripe payment link (real checkout)
                benefit = DEFAULT_BENEFIT
                for h in p.get("hooks", []):
                    if h in BENEFIT_BY_HOOK:
                        benefit = BENEFIT_BY_HOOK[h]
                        break
                try:
                    _stage("host", "running", f"creating checkout for {p['title']}...")
                    pay = lp.create_payment_link(
                        product_name=p["title"],
                        price_usd=p["retail_price"],
                        image_url=p.get("photo_url") or p.get("card_url") or "",
                        description=benefit,
                    )
                    if pay.get("url"):
                        p["payment_link"] = pay["url"]
                    else:
                        _log(f"stripe link failed for {p['title']}: {pay.get('error')}")
                except Exception as e:
                    _log(f"stripe link error for {p['title']}: {e}")

                # 5c. landing page on GitHub Pages
                try:
                    bullets = [benefit,
                               "Tracked delivery on every order",
                               "Secure Stripe checkout",
                               "30-day return window"]
                    if p.get("intent"):
                        bullets.insert(1, f'Buyers online: "{p["intent"][0]}"')
                    html = lp.render_landing_html(
                        product_name=p["title"],
                        photo_url=p.get("photo_url", ""),
                        retail_price=p["retail_price"],
                        compare_at=p["compare_at"],
                        benefit=benefit,
                        bullets=bullets,
                        buy_url=p.get("payment_link") or LANDING_URL or "#",
                    )
                    p["landing_url"] = lp.publish_landing_page(p["product_id"][:30], html)
                    pages_made += 1
                    _stage("host", "running", f"{hosted} ads, {pages_made} store pages live")
                except Exception as e:
                    _log(f"landing page failed for {p['title']}: {e}")

            _stage("host", "done", f"{hosted} ads + {pages_made} store pages + {sum(1 for p in products if p['payment_link'])} checkouts")
        except Exception as e:
            _stage("host", "error", f"publishing unavailable: {e}")
    with _LOCK:
        STATE["products"] = products

    # STAGE 6: post to social
    _stage("post", "running")
    posts = []
    if dry_run:
        _stage("post", "done", "skipped (dry run)")
    else:
        for p in products:
            for platform in platforms:
                entry = {"platform": platform, "product": p["title"], "status": "", "detail": "", "url": ""}
                try:
                    if platform == "pinterest":
                        if not p.get("card_url"):
                            entry["status"] = "skipped"
                            entry["detail"] = "no hosted image"
                        else:
                            # Retail copy: benefit-led, links to the product's own store page
                            desc = (f"{p['title']} — ${p['retail_price']:.2f} today. "
                                    f"Tap to shop with secure checkout. "
                                    f"{' '.join('#' + t for t in p['keyword'].split()[:3])}").strip()
                            shop_link = p.get("landing_url") or LANDING_URL
                            r = requests.post(f"{SOCIAL_URL}/post/pinterest", json={
                                "title": p["title"][:95],
                                "description": desc[:480],
                                "image_url": p["card_url"],
                                "link": shop_link,
                            }, timeout=45)
                            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                            pin_id = (body.get("result") or {}).get("id", "")
                            if r.ok and body.get("status") == "posted" and pin_id:
                                entry["status"] = "posted"
                                entry["url"] = body.get("pin_url") or f"https://www.pinterest.com/pin/{pin_id}/"
                                entry["detail"] = "live on Pinterest"
                            else:
                                entry["status"] = "failed"
                                msg = str(body.get("error", r.text[:150]))
                                if "Trial access" in msg:
                                    msg = ("Pinterest app is in TRIAL mode - Pinterest blocks real pins until "
                                           "you request Standard access at developers.pinterest.com/apps")
                                entry["detail"] = msg
                    elif platform == "youtube":
                        entry["status"] = "skipped"
                        entry["detail"] = "needs video — run Prometheus video job first"
                    elif platform == "tiktok":
                        entry["status"] = "skipped"
                        entry["detail"] = "TikTok OAuth not completed yet"
                    elif platform == "instagram":
                        entry["status"] = "skipped"
                        entry["detail"] = "Meta credentials not configured"
                    else:
                        entry["status"] = "skipped"
                        entry["detail"] = "unknown platform"
                except Exception as e:
                    entry["status"] = "failed"
                    entry["detail"] = str(e)[:200]
                posts.append(entry)
                with _LOCK:
                    STATE["posts"] = posts
                _stage("post", "running", f"{sum(1 for x in posts if x['status']=='posted')} posted so far")

        n_posted = sum(1 for x in posts if x["status"] == "posted")
        n_failed = sum(1 for x in posts if x["status"] == "failed")
        _stage("post", "done", f"{n_posted} posted, {n_failed} failed, {len(posts)-n_posted-n_failed} skipped")

    with _LOCK:
        n_posted = sum(1 for x in posts if x["status"] == "posted")
        STATE["summary"] = (f"{len(products)} products found, {cards_made} cards made, "
                            f"{n_posted} posts live")
    _log("PIPELINE COMPLETE")
