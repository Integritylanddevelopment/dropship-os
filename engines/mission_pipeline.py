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
LIBRARY_PATH = SHIPSTACK_ROOT / "data" / "product_library.json"


def _variant_public(v: dict) -> dict:
    """Library-safe view of an ad variant (filename, not full path)."""
    return {
        "file": Path(v["path"]).name if v.get("path") else v.get("file", ""),
        "url": v.get("url", ""),
        "headline": v.get("headline", ""),
        "subline": v.get("subline", ""),
        "archetype": v.get("archetype", ""),
        "advisor": v.get("advisor", ""),
        "grade": v.get("grade", 0),
        "letter": v.get("letter", "?"),
        "photo": v.get("photo", ""),
        "badge": v.get("badge", ""),
        "cta": v.get("cta", ""),
        "approved": v.get("approved", False),
        "approved_at": v.get("approved_at", ""),
    }


def save_to_library(products: list, query: str | None):
    """Persist every gathered product + its collateral. Survives restarts."""
    try:
        lib = {}
        if LIBRARY_PATH.exists():
            lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8", errors="replace"))
        for p in products:
            pid = p.get("product_id")
            if not pid:
                continue
            old = lib.get(pid, {})
            entry = {
                "product_id": pid,
                "title": p.get("title") or old.get("title", ""),
                "keyword": p.get("keyword") or old.get("keyword", ""),
                "query": query or old.get("query", ""),
                "score": p.get("score", old.get("score", 0)),
                "retail_price": p.get("retail_price") or old.get("retail_price", 0),
                "compare_at": p.get("compare_at") or old.get("compare_at", 0),
                "margin_pct": p.get("margin_pct", old.get("margin_pct", 0)),
                "photo_url": p.get("photo_url") or old.get("photo_url", ""),
                "cj_pid": p.get("cj_pid") or old.get("cj_pid", ""),
                "supplier_title": p.get("supplier_title") or old.get("supplier_title", ""),
                "intent": p.get("intent") or old.get("intent", []),
                "landing_url": p.get("landing_url") or old.get("landing_url", ""),
                "payment_link": p.get("payment_link") or old.get("payment_link", ""),
                "top_grade": p.get("top_grade") or old.get("top_grade", ""),
                "ad_variants": ([_variant_public(v) for v in p.get("ad_variants") or []]
                                or old.get("ad_variants", [])),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            lib[pid] = entry
        LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        LIBRARY_PATH.write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        _log(f"library save failed: {e}")


def load_library() -> list:
    """All products ever gathered, newest first. Backfills from run history
    the first time (so nothing already built gets lost)."""
    if not LIBRARY_PATH.exists() and RUNS_LOG.exists():
        # Backfill from past run snapshots
        try:
            for line in RUNS_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    snap = json.loads(line)
                    prods = snap.get("products") or []
                    for p in prods:
                        if p.get("ad_variants"):
                            for v in p["ad_variants"]:
                                v.setdefault("path", v.get("file", ""))
                    save_to_library(prods, snap.get("query"))
                except Exception:
                    continue
        except Exception:
            pass
    try:
        lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8", errors="replace"))
        items = list(lib.values())
        items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return items
    except Exception:
        return []

SOCIAL_URL = os.getenv("SOCIAL_AI_URL", "http://127.0.0.1:8867")
PROMETHEUS_URL = os.getenv("PROMETHEUS_ENGINE_URL", "http://127.0.0.1:8766")
LANDING_URL = os.getenv("LANDING_PAGE_URL", "")
QUINN_URL = os.getenv("QUINN_ENDPOINT", "http://127.0.0.1:8765")
QUINN_MODEL = os.getenv("SHIPSTACK_MODEL", "qwen2.5:7b")


def _quinn_copy(product_title: str, keyword: str, quote: str = "") -> tuple[str, str]:
    """Ask Quinn (local AI) to write the ad headline + pin description.
    Returns (headline, description) — empty strings if Quinn can't answer,
    in which case the caller falls back to templates. Never blocks a run."""
    try:
        hint = f' A real buyer comment about it: "{quote}".' if quote else ""
        r = requests.post(f"{QUINN_URL}/v1/chat/completions", json={
            "model": QUINN_MODEL,
            "messages": [{
                "role": "user",
                "content": (
                    f"You write short retail ad copy. Product: '{product_title}' "
                    f"(category: {keyword}).{hint}\n"
                    "Reply with EXACTLY two lines:\n"
                    "HEADLINE: <max 8 words, benefit the buyer gets, no hype words>\n"
                    "DESC: <max 22 words, for a Pinterest pin, ends with a reason to tap>"
                ),
            }],
            "max_tokens": 120,
            "temperature": 0.8,
        }, timeout=30)
        content = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
        headline, desc = "", ""
        for ln in content.splitlines():
            s = ln.strip()
            if s.upper().startswith("HEADLINE:"):
                headline = s.split(":", 1)[1].strip().strip('"')
            elif s.upper().startswith("DESC:"):
                desc = s.split(":", 1)[1].strip().strip('"')
        return headline[:80], desc[:200]
    except Exception:
        return "", ""

def _clean_title(raw: str, max_len: int = 48) -> str:
    """Turn a supplier listing title into a clean retail product name."""
    import re as _re
    if not raw:
        return ""
    t = _re.sub(r"\[.*?\]|\(.*?\)", " ", raw)          # drop bracketed noise
    t = t.split("|")[0].split(",")[0]                   # first clause only
    # Strip supplier-listing junk prefixes
    t = _re.sub(r"^(manufacturer'?s?|wholesale|hot sale|new|2\d{3})\s+", "", t, flags=_re.I)
    t = _re.sub(r"\s+", " ", t).strip()
    if t.isupper():
        t = t.title()
    # Fix title-case artifacts like "Manufacturer'S"
    t = t.replace("'S ", "'s ").replace("’S ", "’s ")
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


def _now_central() -> str:
    """Chicago time, 12-hour clock — e.g. '2:07:33 PM'."""
    try:
        from zoneinfo import ZoneInfo
        t = datetime.now(ZoneInfo("America/Chicago"))
    except Exception:
        t = datetime.now()
    return t.strftime("%I:%M:%S %p").lstrip("0")


def _log(msg: str):
    line = f"{_now_central()}  ·  {msg}"
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


# ── On-demand regeneration (per product / per ad) ────────────────────────
REGEN = {"running": False, "product_id": None, "variant": None,
         "detail": "", "error": None, "finished_at": None}


def get_regen_status() -> dict:
    with _LOCK:
        return dict(REGEN)


def _regen_detail(msg: str):
    with _LOCK:
        REGEN["detail"] = msg
    _log(msg)


def set_ad_approval(product_id: str, variant_index: int, approved: bool = True) -> dict:
    """Mark one ad approved (ready for Mike to post) or pull it back."""
    try:
        lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "error": "library not found"}
    entry = lib.get(product_id)
    if not entry:
        return {"ok": False, "error": "product not found"}
    ads = entry.get("ad_variants") or []
    if not (0 <= variant_index < len(ads)):
        return {"ok": False, "error": "ad not found"}
    ads[variant_index]["approved"] = bool(approved)
    ads[variant_index]["approved_at"] = (datetime.now(timezone.utc).isoformat()
                                         if approved else "")
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    lib[product_id] = entry
    LIBRARY_PATH.write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "approved": bool(approved)}


def load_approved() -> list:
    """Mike's feed: products that have at least one APPROVED ad, with only
    the approved ads included. Everything else stays invisible to him."""
    out = []
    for p in load_library():
        approved = [v for v in (p.get("ad_variants") or []) if v.get("approved")]
        if not approved:
            continue
        out.append({
            "product_id": p.get("product_id"),
            "title": p.get("title"),
            "retail_price": p.get("retail_price"),
            "landing_url": p.get("landing_url"),
            "payment_link": p.get("payment_link"),
            "approved_ads": [{
                "image_url": v.get("url", ""),
                "file": v.get("file", ""),
                "headline": v.get("headline", ""),
                "subline": v.get("subline", ""),
                "grade": v.get("grade", 0),
                "letter": v.get("letter", "?"),
                "approved_at": v.get("approved_at", ""),
            } for v in approved],
        })
    return out


def start_regen(product_id: str, variant_index: int | None = None) -> dict:
    """Rebuild all 10 ads for a product, or retry ONE ad (context-injected)."""
    with _LOCK:
        if REGEN["running"]:
            return {"ok": False, "error": "Another ad job is already running — give it a minute"}
        REGEN.update({"running": True, "product_id": product_id,
                      "variant": variant_index, "detail": "starting...",
                      "error": None, "finished_at": None})
    t = threading.Thread(target=_run_regen, args=(product_id, variant_index), daemon=True)
    t.start()
    return {"ok": True}


def _run_regen(product_id: str, variant_index: int | None):
    try:
        _do_regen(product_id, variant_index)
        with _LOCK:
            REGEN["error"] = None
    except Exception as e:
        traceback.print_exc()
        with _LOCK:
            REGEN["error"] = str(e)[:300]
        _log(f"Ad job failed: {e}")
    finally:
        with _LOCK:
            REGEN["running"] = False
            REGEN["finished_at"] = datetime.now(timezone.utc).isoformat()


def _do_regen(product_id: str, variant_index: int | None):
    sys.path.insert(0, str(SHIPSTACK_ROOT))
    from asset_machine.collateral_engine import (
        build_copy_variants, ai_copy_set, ai_retry_copy, build_photo_pool,
        grade_copy, improve_offer, render_variant, PALETTES, _fetch_photo,
    )
    from integrations.github_image_host import upload_image

    lib = {}
    if LIBRARY_PATH.exists():
        lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8", errors="replace"))
    entry = lib.get(product_id)
    if not entry:
        raise RuntimeError(f"Product '{product_id}' not found in library")
    title = entry.get("title", product_id)

    # 1. Fresh image pool — DIFFERENT pictures, not the same one again
    _regen_detail(f"Hunting for more photos of {title}...")
    pool = build_photo_pool(entry)
    _regen_detail(f"Found {len(pool)} product photos to work with")

    photo_cache: dict = {}

    def photo_for(url):
        if not url:
            return None
        if url not in photo_cache:
            photo_cache[url] = _fetch_photo(url)
        return photo_cache[url]

    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    if variant_index is None:
        # ── Full rebuild: 10 fresh ads, AI-first product-specific copy ──
        variants = build_copy_variants(entry)
        archetypes = [v["archetype"] for v in variants]
        _regen_detail(f"ALIEN is writing 10 original ads for {title}...")
        ai = ai_copy_set(entry, archetypes)
        for i, v in enumerate(variants):
            if i in ai:
                v["headline"], v["subline"] = ai[i]
                v["juiced"] = True
        for v in variants:
            g = grade_copy(v, entry)
            if g["total"] < 70:
                v = improve_offer(v, entry, g)
                g = grade_copy(v, entry)
            v["grade"], v["letter"] = g["total"], g["letter"]
        variants.sort(key=lambda v: v.get("grade", 0), reverse=True)

        new_variants = []
        for i, copy in enumerate(variants):
            purl = pool[i % len(pool)] if pool else entry.get("photo_url", "")
            _regen_detail(f"Rendering ad {i+1} of {len(variants)} for {title} (grade {copy['letter']})")
            path = str(CARDS_DIR / f"{product_id[:28]}_v{i+1}.png")
            res = render_variant(entry, copy, layout=i % 5, palette_i=i % len(PALETTES),
                                 out_path=path, photo=photo_for(purl))
            if not res:
                continue
            url = ""
            try:
                url = upload_image(res, dest_name=Path(res).name)
            except Exception as e:
                _log(f"upload failed for ad {i+1}: {e}")
            new_variants.append({"file": Path(res).name, "url": url,
                                 "headline": copy["headline"], "subline": copy.get("subline", ""),
                                 "archetype": copy["archetype"], "advisor": copy["advisor"],
                                 "grade": copy.get("grade", 0), "letter": copy.get("letter", "?"),
                                 "photo": purl, "badge": copy.get("badge", ""),
                                 "cta": copy.get("cta", "")})
        entry["ad_variants"] = new_variants
        if new_variants:
            entry["top_grade"] = f"{new_variants[0]['letter']} ({new_variants[0]['grade']})"
        if pool and not entry.get("photo_url"):
            entry["photo_url"] = pool[0]

        # Refresh the sales page too — better copy every time ads are redone
        if entry.get("payment_link"):
            try:
                from asset_machine.collateral_engine import ai_landing_copy
                from integrations import landing_pages as lp
                _regen_detail(f"Rewriting the sales page for {title}...")
                page = ai_landing_copy(entry)
                html = lp.render_landing_html(
                    product_name=title,
                    photo_url=entry.get("photo_url", ""),
                    retail_price=entry.get("retail_price", 0),
                    compare_at=entry.get("compare_at", 0),
                    benefit=page["headline"],
                    bullets=page["bullets"],
                    buy_url=entry["payment_link"],
                    headline=page["headline"],
                    paragraph=page["paragraph"],
                    quote=(entry.get("intent") or [""])[0],
                )
                entry["landing_url"] = lp.publish_landing_page(product_id[:30], html)
            except Exception as e:
                _log(f"sales page refresh failed: {e}")
        _regen_detail(f"{title}: {len(new_variants)} new ads live")
    else:
        # ── Single-ad retry: context injection — the reject + all other ads ──
        ads = entry.get("ad_variants") or []
        if not (0 <= variant_index < len(ads)):
            raise RuntimeError("That ad number doesn't exist")
        old = ads[variant_index]
        others = [a.get("headline", "") for j, a in enumerate(ads) if j != variant_index]
        _regen_detail(f"ALIEN is rewriting ad {variant_index+1} for {title} (told: don't repeat the other {len(others)})")
        head, sub = ai_retry_copy(entry, old.get("archetype", "proof_direct"), old, others)
        # Rebuild a COMPLETE copy dict — saved ads may lack badge/cta fields
        base = next((v for v in build_copy_variants(entry)
                     if v["archetype"] == old.get("archetype")), None)
        copy = dict(base) if base else {
            "archetype": old.get("archetype", "proof_direct"),
            "advisor": old.get("advisor", ""), "badge": "TRENDING NOW",
            "cta": "SHOP NOW", "headline": old.get("headline", ""),
            "subline": old.get("subline", ""),
        }
        if old.get("badge"):
            copy["badge"] = old["badge"]
        if old.get("cta"):
            copy["cta"] = old["cta"]
        if head:
            copy["headline"], copy["subline"] = head, sub
        else:
            copy["headline"] = old.get("headline") or copy["headline"]
            copy["subline"] = old.get("subline") or copy["subline"]
            _log("AI didn't answer — reshuffling design + photo instead")
        g = grade_copy(copy, entry)
        if g["total"] < 70:
            copy = improve_offer(copy, entry, g)
            g = grade_copy(copy, entry)
        copy["grade"], copy["letter"] = g["total"], g["letter"]

        # Pick a DIFFERENT photo than the ad had before
        cur_photo = old.get("photo") or entry.get("photo_url", "")
        purl = next((u for u in pool if u != cur_photo), cur_photo)
        # New layout + palette too, so the retry FEELS different
        new_layout = (variant_index + 3) % 5
        new_palette = (variant_index + 2) % len(PALETTES)

        _regen_detail(f"Rendering the new take on ad {variant_index+1}...")
        fname = old.get("file") or f"{product_id[:28]}_v{variant_index+1}.png"
        path = str(CARDS_DIR / fname)
        res = render_variant(entry, copy, layout=new_layout, palette_i=new_palette,
                             out_path=path, photo=photo_for(purl))
        if not res:
            raise RuntimeError("Render failed")
        url = old.get("url", "")
        try:
            url = upload_image(res, dest_name=Path(res).name)
        except Exception as e:
            _log(f"upload failed: {e}")
        ads[variant_index] = {"file": Path(res).name, "url": url,
                              "headline": copy["headline"], "subline": copy.get("subline", ""),
                              "archetype": copy["archetype"], "advisor": copy.get("advisor", ""),
                              "grade": copy["grade"], "letter": copy["letter"],
                              "photo": purl, "badge": copy.get("badge", ""),
                              "cta": copy.get("cta", "")}
        entry["ad_variants"] = ads
        _regen_detail(f"Ad {variant_index+1} for {title} redone — grade {copy['letter']} ({copy['grade']})")

    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    lib[product_id] = entry
    LIBRARY_PATH.write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")


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
    detail = (f"Social poster {'online' if svc['social'] else 'OFFLINE'}, "
              f"video engine {'online' if svc['prometheus'] else 'OFFLINE'}")
    _stage("services", "done", detail)
    if not svc["social"] and not dry_run and platforms:
        _log("Heads up: the social poster is offline, so posting will fail this run.")

    # STAGE 2: discover
    _stage("discover", "running", "Scanning Reddit and Google Trends for what people want to buy...")
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
    _stage("discover", "done", f"Read {result.get('total_signals', 0)} posts and found {len(reports)} product ideas")

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
            _log(f"Skipped '{r.get('product_keyword')}' — not a sellable product name")
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
    _stage("pick", "done", f"Picked the {len(products)} best out of {len(viable)} candidates")

    # Write decisions.json for compatibility with existing tools
    try:
        with open(DECISIONS_PATH, "w", encoding="utf-8") as f:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                       "count": len(products), "products": products}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log(f"decisions.json write failed: {e}")

    # STAGE 4: retail ads — match a real supplier product, price it, build the ad
    _stage("content", "running", "Matching products to real suppliers...")
    cards_made = 0
    sys.path.insert(0, str(SHIPSTACK_ROOT))
    from social_ai_agent.retail_ad_card import generate_retail_ad
    from discovery_engine.suppliers import cj_dropshipping
    from discovery_engine.scoring import margin_calc

    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(products, 1):
        # 4a. Find a real supplier listing (photo + true cost)
        try:
            _stage("content", "running", f"Finding a supplier for '{p['keyword']}' ({i} of {len(products)})...")
            listings = cj_dropshipping.search(p["keyword"], limit=5)
            best = next((l for l in listings if l.get("image") and (l.get("unit_cost") or 0) > 0), None)
            if best:
                p["photo_url"] = best["image"]
                p["supplier_title"] = (best.get("title") or "")[:120]
                p["supplier_cost"] = float(best["unit_cost"])
                p["cj_pid"] = best.get("id", "")  # needed for auto-fulfillment
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

        # 4c. Marketing Collateral Engine: 10 graded ads per product
        # (advisor playbooks -> ALIEN GPU copy -> Hormozi grading -> render)
        try:
            from asset_machine.collateral_engine import generate_collateral_set
            _stage("content", "running", f"Collateral engine: building 10 ads for {p['title']}...")
            variants = generate_collateral_set(
                p, out_dir=str(CARDS_DIR), n=10, use_ai=True,
                progress_cb=lambda m: _stage("content", "running", f"{p['title']}: {m}"),
            )
            p["ad_variants"] = variants
            if variants:
                p["card_path"] = variants[0]["path"]
                p["headline"] = variants[0]["headline"]
                p["ad_copy"] = variants[0].get("subline", "")
                p["top_grade"] = f"{variants[0]['letter']} ({variants[0]['grade']})"
                cards_made += len(variants)
                juiced = sum(1 for v in variants if v.get("grade", 0) >= 65)
                _log(f"{p['title']}: {len(variants)} ads built — best grade {p['top_grade']}, {juiced} graded B or higher")
        except Exception as e:
            _log(f"collateral engine failed for {p['title']}: {e}")
    with _LOCK:
        STATE["products"] = products
    with_photos = sum(1 for p in products if p["photo_url"])
    _stage("content", "done", f"Built {cards_made} ads — {with_photos} with real product photos")

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
                # 5a. host ALL ad variants (10 per product, one campaign)
                for vi, v in enumerate(p.get("ad_variants") or [], 1):
                    try:
                        vname = Path(v["path"]).name
                        v["url"] = upload_image(v["path"], dest_name=vname)
                        hosted += 1
                        if vi % 3 == 0:
                            _stage("host", "running", f"{hosted} ads published so far...")
                    except Exception as e:
                        _log(f"ad upload failed ({p['title']} v{vi}): {e}")
                if p.get("ad_variants"):
                    p["card_url"] = next((v.get("url") for v in p["ad_variants"] if v.get("url")), None)
                elif p.get("card_path"):
                    try:
                        p["card_url"] = upload_image(p["card_path"], dest_name=f"{p['product_id'][:30]}.png")
                        hosted += 1
                    except Exception as e:
                        _log(f"image host failed for {p['title']}: {e}")

                # 5b. Stripe payment link (real checkout)
                benefit = p.get("headline") or DEFAULT_BENEFIT
                if not p.get("headline"):
                    for h in p.get("hooks", []):
                        if h in BENEFIT_BY_HOOK:
                            benefit = BENEFIT_BY_HOOK[h]
                            break
                try:
                    _stage("host", "running", f"Setting up secure checkout for {p['title']}...")
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

                # 5c. landing page on GitHub Pages (full sales copy)
                try:
                    from asset_machine.collateral_engine import ai_landing_copy
                    page = ai_landing_copy(p)
                    html = lp.render_landing_html(
                        product_name=p["title"],
                        photo_url=p.get("photo_url", ""),
                        retail_price=p["retail_price"],
                        compare_at=p["compare_at"],
                        benefit=benefit,
                        bullets=page["bullets"],
                        buy_url=p.get("payment_link") or LANDING_URL or "#",
                        headline=page["headline"],
                        paragraph=page["paragraph"],
                        quote=(p.get("intent") or [""])[0],
                    )
                    p["landing_url"] = lp.publish_landing_page(p["product_id"][:30], html)
                    pages_made += 1
                    _stage("host", "running", f"{hosted} ads published, {pages_made} store pages live")
                except Exception as e:
                    _log(f"landing page failed for {p['title']}: {e}")

            n_pay = sum(1 for p in products if p['payment_link'])
            _stage("host", "done", f"{hosted} ads, {pages_made} store pages, {n_pay} checkouts — all live")
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
                        # Post the TOP-GRADED ad variants (up to 3 per product per
                        # run to avoid spam flags) — every one links to the SAME
                        # sales page for this product.
                        shop_link = p.get("landing_url") or LANDING_URL
                        # Only APPROVED ads ever get posted — Alex reviews first
                        postable = [v for v in (p.get("ad_variants") or [])
                                    if v.get("url") and v.get("approved")][:3]
                        if not postable:
                            entry["status"] = "skipped"
                            entry["detail"] = "waiting for your approval — approve ads in the Library"
                        else:
                            n_ok, last_msg, first_url = 0, "", ""
                            for v in postable:
                                desc = (f"{v.get('subline') or p['title']} "
                                        f"{' '.join('#' + t for t in p['keyword'].split()[:3])}").strip()
                                try:
                                    r = requests.post(f"{SOCIAL_URL}/post/pinterest", json={
                                        "title": (v.get("headline") or p["title"])[:95],
                                        "description": desc[:480],
                                        "image_url": v["url"],
                                        "link": shop_link,
                                    }, timeout=45)
                                    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                                    pin_id = (body.get("result") or {}).get("id", "")
                                    if r.ok and body.get("status") == "posted" and pin_id:
                                        n_ok += 1
                                        if not first_url:
                                            first_url = body.get("pin_url") or f"https://www.pinterest.com/pin/{pin_id}/"
                                    else:
                                        last_msg = str(body.get("error", r.text[:150]))
                                except Exception as e:
                                    last_msg = str(e)[:150]
                            if n_ok:
                                entry["status"] = "posted"
                                entry["url"] = first_url
                                entry["detail"] = f"{n_ok} of {len(postable)} ads live (all -> one sales page)"
                            else:
                                entry["status"] = "failed"
                                if "Trial access" in last_msg:
                                    last_msg = ("Pinterest app is in TRIAL mode - Pinterest blocks real pins until "
                                                "you request Standard access at developers.pinterest.com/apps")
                                entry["detail"] = last_msg
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
        n_skip = len(posts) - n_posted - n_failed
        _stage("post", "done", f"{n_posted} live, {n_failed} blocked, {n_skip} skipped — details in the table below")

    with _LOCK:
        n_posted = sum(1 for x in posts if x["status"] == "posted")
        n_pages = sum(1 for p in products if p.get("landing_url"))
        STATE["summary"] = (f"{len(products)} products, {cards_made} ads, "
                            f"{n_pages} store pages with checkout, {n_posted} social posts live")
    save_to_library(products, query)
    _log("All done — this run is complete. Products saved to the library.")
