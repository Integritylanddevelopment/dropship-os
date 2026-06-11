"""produced.py - browse + curate Prometheus-produced video variants.

Scans engines/prometheus_output/<slug>/<platform>.mp4
Extracts a first-frame thumbnail via ffmpeg (cached as <platform>_thumb.jpg).
Manages per-product, per-platform selection state for push-to-social.
"""
import os, sys, json, pathlib, subprocess
from datetime import datetime
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

ROOT = pathlib.Path(r"C:/Users/integ/Documents/Claude/Projects/ShipStack")
PROD_DIR = ROOT / "engines" / "prometheus_output"
STATE = ROOT / "dashboard" / "state"
STATE.mkdir(parents=True, exist_ok=True)
SELECTIONS_FILE = STATE / "produced_selections.json"
SOCIAL_READY_FILE = STATE / "social_ready.json"
MEDIA_KITS_FILE = STATE / "media_kits.json"

PLATFORM_DIMS = {
    "tiktok": (1080, 1920),
    "instagram_reels": (1080, 1920),
    "youtube_shorts": (1080, 1920),
    "pinterest": (1000, 1500),
}

def slugify(s):
    import re
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "product")).strip("_").lower()
    return s[:48] or "product"

def _ffprobe_duration(mp4_path):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(mp4_path)],
            stderr=subprocess.STDOUT, timeout=8
        ).decode("utf-8", "replace").strip()
        return float(out) if out else None
    except Exception:
        return None

def _ensure_thumb(mp4_path, thumb_path):
    if thumb_path.exists() and thumb_path.stat().st_size > 0:
        return True
    try:
        subprocess.check_output(
            ["ffmpeg", "-y", "-ss", "0.5", "-i", str(mp4_path),
             "-frames:v", "1", "-vf", "scale=480:-2", str(thumb_path)],
            stderr=subprocess.STDOUT, timeout=12
        )
        return thumb_path.exists() and thumb_path.stat().st_size > 0
    except Exception:
        return False

def scan_produced():
    out = {}
    if not PROD_DIR.exists():
        return out
    for slug_dir in sorted(PROD_DIR.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        per_platform = {}
        for mp4 in slug_dir.glob("*.mp4"):
            platform = mp4.stem
            thumb = slug_dir / f"{platform}_thumb.jpg"
            _ensure_thumb(mp4, thumb)
            try:
                stat = mp4.stat()
                size_bytes = stat.st_size
                generated_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            except Exception:
                size_bytes = 0
                generated_at = None
            duration_sec = _ffprobe_duration(mp4)
            w, h = PLATFORM_DIMS.get(platform, (1080, 1920))
            per_platform[platform] = {
                "mp4_path": str(mp4),
                "mp4_url": f"/api/produced/file/{slug}/{mp4.name}",
                "thumb_path": str(thumb) if thumb.exists() else None,
                "thumb_url": f"/api/produced/file/{slug}/{thumb.name}" if thumb.exists() else None,
                "duration_sec": duration_sec,
                "dimensions": f"{w}x{h}",
                "size_bytes": size_bytes,
                "generated_at": generated_at,
                "filename": mp4.name,
                "thumb_filename": thumb.name if thumb.exists() else None,
            }
        if per_platform:
            out[slug] = per_platform
    return out

def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)

def get_selections():
    return _load_json(SELECTIONS_FILE, {})

def select_for_social(product_keyword, platform, selected):
    slug = slugify(product_keyword)
    sel = get_selections()
    if slug not in sel:
        sel[slug] = {}
    if selected:
        sel[slug][platform] = True
    else:
        sel[slug].pop(platform, None)
        if not sel[slug]:
            sel.pop(slug, None)
    _save_json(SELECTIONS_FILE, sel)
    return {"slug": slug, "platform": platform, "selected": bool(selected),
            "product_keyword": product_keyword}

def _load_media_kits():
    return _load_json(MEDIA_KITS_FILE, {})

def push_to_social_ready(product_keyword):
    slug = slugify(product_keyword)
    sel = get_selections()
    prod = scan_produced().get(slug, {})
    kits = _load_media_kits()
    kit = kits.get(product_keyword) or kits.get(slug) or {}

    selected_for_slug = sel.get(slug, {})
    if not selected_for_slug:
        return {"moved": [], "product_keyword": product_keyword, "slug": slug,
                "note": "no selections"}

    ready = _load_json(SOCIAL_READY_FILE, {})
    if product_keyword not in ready:
        ready[product_keyword] = {"slug": slug, "items": []}
    elif "items" not in ready[product_keyword]:
        ready[product_keyword]["items"] = []

    existing_ids = {it.get("item_id") for it in ready[product_keyword]["items"]}
    moved = []
    now = datetime.now().isoformat(timespec="seconds")
    for platform, _flag in selected_for_slug.items():
        if platform not in prod:
            continue
        meta = prod[platform]
        item_id = f"{slug}__{platform}"
        if item_id in existing_ids:
            for it in ready[product_keyword]["items"]:
                if it.get("item_id") == item_id:
                    it["mp4_path"] = meta.get("mp4_path")
                    it["mp4_url"] = meta.get("mp4_url")
                    it["thumb_url"] = meta.get("thumb_url")
                    it["duration_sec"] = meta.get("duration_sec")
                    it["dimensions"] = meta.get("dimensions")
                    it["size_bytes"] = meta.get("size_bytes")
                    it["updated_at"] = now
                    if it.get("status") not in ("posted",):
                        it["status"] = "queued"
                    moved.append(it)
                    break
            continue
        item = {
            "item_id": item_id,
            "platform": platform,
            "product_keyword": product_keyword,
            "slug": slug,
            "mp4_path": meta.get("mp4_path"),
            "mp4_url": meta.get("mp4_url"),
            "thumb_url": meta.get("thumb_url"),
            "duration_sec": meta.get("duration_sec"),
            "dimensions": meta.get("dimensions"),
            "size_bytes": meta.get("size_bytes"),
            "hook": kit.get("hook") or "",
            "caption": kit.get("caption") or "",
            "hashtags": kit.get("hashtags") or [],
            "image_url": kit.get("image_url") or "",
            "status": "queued",
            "selected_for_live": False,
            "moved_at": now,
            "updated_at": now,
        }
        ready[product_keyword]["items"].append(item)
        moved.append(item)

    _save_json(SOCIAL_READY_FILE, ready)
    sel.pop(slug, None)
    _save_json(SELECTIONS_FILE, sel)

    return {"moved": moved, "product_keyword": product_keyword, "slug": slug,
            "count": len(moved)}