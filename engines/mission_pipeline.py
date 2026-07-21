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

STAGE_NAMES = ["services", "discover", "pick", "content", "host", "post"]
STAGE_LABELS = {
    "services": "Check services",
    "discover": "Discover trending products",
    "pick": "Pick winners",
    "content": "Generate content cards",
    "host": "Publish images",
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
    winners = viable[:limit]

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

    # STAGE 4: content cards
    _stage("content", "running")
    cards_made = 0
    try:
        sys.path.insert(0, str(SHIPSTACK_ROOT))
        from social_ai_agent.pinterest_poster import generate_product_card
        CARDS_DIR.mkdir(parents=True, exist_ok=True)
        for p in products:
            out = str(CARDS_DIR / f"{p['product_id'][:30]}_card.png")
            try:
                res = generate_product_card(
                    product=p["title"],
                    niche=p["keyword"],
                    margin=round(p["margin_pct"] * 100, 1),
                    score=round(p["score"] * 100, 1),
                    output_path=out,
                )
                if res:
                    p["card_path"] = res
                    cards_made += 1
                    _stage("content", "running", f"card {cards_made}/{len(products)}: {p['title']}")
            except Exception as e:
                _log(f"card failed for {p['title']}: {e}")
    except ImportError as e:
        _log(f"card generator unavailable: {e}")
    with _LOCK:
        STATE["products"] = products
    _stage("content", "done", f"{cards_made}/{len(products)} cards generated")

    # STAGE 5: host images (GitHub -> public URLs)
    _stage("host", "running")
    hosted = 0
    if dry_run:
        _stage("host", "done", "skipped (dry run)")
    else:
        try:
            from integrations.github_image_host import upload_image
            for p in products:
                if not p.get("card_path"):
                    continue
                try:
                    url = upload_image(p["card_path"], dest_name=f"{p['product_id'][:30]}.png")
                    p["card_url"] = url
                    hosted += 1
                    _stage("host", "running", f"published {hosted} images")
                except Exception as e:
                    _log(f"image host failed for {p['title']}: {e}")
            _stage("host", "done", f"{hosted} images published" if hosted else "no images published")
        except Exception as e:
            _stage("host", "error", f"image hosting unavailable: {e}")
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
                            desc = (f"{p['title']} — trending {p['keyword']} find. "
                                    f"{' '.join('#' + h.replace('-', '') for h in p.get('hooks', []))}").strip()
                            r = requests.post(f"{SOCIAL_URL}/post/pinterest", json={
                                "title": p["title"][:95],
                                "description": desc[:480],
                                "image_url": p["card_url"],
                                "link": LANDING_URL,
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
