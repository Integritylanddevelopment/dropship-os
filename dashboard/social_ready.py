"""social_ready.py - manage items staged for live publishing."""
import os, sys, json, pathlib
from datetime import datetime
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

ROOT = pathlib.Path(r"C:/Users/integ/Documents/Claude/Projects/ShipStack")
STATE = ROOT / "dashboard" / "state"
STATE.mkdir(parents=True, exist_ok=True)
SOCIAL_READY_FILE = STATE / "social_ready.json"

def _load():
    if not SOCIAL_READY_FILE.exists():
        return {}
    try:
        return json.loads(SOCIAL_READY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save(data):
    tmp = SOCIAL_READY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(SOCIAL_READY_FILE)

def list_ready():
    return _load()

def select_for_live(product_keyword, platform, item_id, selected):
    data = _load()
    bucket = data.get(product_keyword)
    if not bucket:
        return {"error": "product not in social_ready", "product_keyword": product_keyword}
    found = None
    for it in bucket.get("items", []):
        if it.get("item_id") == item_id and it.get("platform") == platform:
            it["selected_for_live"] = bool(selected)
            if selected:
                if it.get("status") in ("queued", "held_no_credential"):
                    it["status"] = "selected_for_live"
            else:
                if it.get("status") == "selected_for_live":
                    it["status"] = "queued"
            it["updated_at"] = datetime.now().isoformat(timespec="seconds")
            found = it
            break
    if not found:
        return {"error": "item not found", "item_id": item_id}
    _save(data)
    return {"ok": True, "item": found}

def publish_live(product_keyword):
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).parent))
    try:
        import social_push
    except Exception as e:
        return {"error": f"social_push import failed: {type(e).__name__}: {e}"}

    data = _load()
    bucket = data.get(product_keyword)
    if not bucket:
        return {"error": "product not in social_ready", "product_keyword": product_keyword}

    summary = {"product_keyword": product_keyword, "results": [],
               "posted": 0, "held": 0, "skipped": 0, "errors": 0}
    now = datetime.now().isoformat(timespec="seconds")
    for it in bucket.get("items", []):
        platform = it.get("platform")
        if not it.get("selected_for_live"):
            summary["skipped"] += 1
            summary["results"].append({"item_id": it.get("item_id"),
                                        "platform": platform,
                                        "action": "skipped",
                                        "reason": "not selected"})
            continue
        if it.get("status") == "posted":
            summary["skipped"] += 1
            summary["results"].append({"item_id": it.get("item_id"),
                                        "platform": platform,
                                        "action": "skipped",
                                        "reason": "already posted"})
            continue
        try:
            connected = social_push.is_connected(platform)
        except Exception:
            connected = False
        if not connected:
            it["status"] = "held_no_credential"
            it["updated_at"] = now
            it["selected_for_live"] = False
            summary["held"] += 1
            summary["results"].append({"item_id": it.get("item_id"),
                                        "platform": platform,
                                        "action": "held_no_credential",
                                        "env_var": (social_push.DRIVERS.get(platform) or {}).get("env_var")})
            continue
        kit = {
            "product_keyword": it.get("product_keyword"),
            "hook": it.get("hook"),
            "caption": it.get("caption"),
            "hashtags": it.get("hashtags"),
            "image_url": it.get("image_url"),
            "mp4_path": it.get("mp4_path"),
            "pillar": it.get("pillar") or "education",
        }
        try:
            entry = social_push.queue_post(platform, kit)
        except Exception as e:
            it["status"] = "error"
            it["last_error"] = f"{type(e).__name__}: {e}"
            it["updated_at"] = now
            summary["errors"] += 1
            summary["results"].append({"item_id": it.get("item_id"),
                                        "platform": platform,
                                        "action": "error",
                                        "error": it["last_error"]})
            continue
        st = entry.get("status") if isinstance(entry, dict) else None
        if st in ("ready", "doctrine_warn"):
            it["status"] = "posted"
            it["posted_at"] = now
            it["selected_for_live"] = False
            summary["posted"] += 1
            summary["results"].append({"item_id": it.get("item_id"),
                                        "platform": platform,
                                        "action": "posted",
                                        "queue_status": st})
        else:
            it["status"] = "queue_blocked"
            it["queue_block_reason"] = (entry or {}).get("rejection_reason") if isinstance(entry, dict) else None
            it["updated_at"] = now
            it["selected_for_live"] = False
            summary["held"] += 1
            summary["results"].append({"item_id": it.get("item_id"),
                                        "platform": platform,
                                        "action": "queue_blocked",
                                        "reason": it.get("queue_block_reason"),
                                        "queue_status": st})
    _save(data)
    return summary