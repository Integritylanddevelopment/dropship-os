"""collateral_scraper.py - per-product collateral capture for ShipStack.

Pure logic; no HTTP. Drives storage under dashboard/state/collateral/<slug>/.

Public:
  scrape_product(product_keyword, report) -> dict
  list_collateral(product_keyword)        -> dict
  add_collateral(product_keyword, source_url=None, uploaded_bytes=None, filename=None) -> dict
  delete_collateral(product_keyword, item_id) -> dict
  product_dir(product_keyword)            -> pathlib.Path
"""
import os, re, sys, json, time, uuid, html, hashlib, pathlib, urllib.parse, urllib.request, urllib.error, threading
from datetime import datetime
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

BASE_DIR = pathlib.Path(__file__).parent.resolve()
STATE_DIR = BASE_DIR / "state" / "collateral"
STATE_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (ShipStack/Collateral Scraper)"
TIMEOUT = 20
MAX_BYTES = 25 * 1024 * 1024  # 25 MB per asset cap
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VID_EXT = {".mp4", ".webm", ".mov", ".m4v"}

_LOCK = threading.Lock()


# ---------- utilities ----------

def slugify(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "product")).strip("_").lower()
    return s[:48] or "product"


def product_dir(product_keyword):
    d = STATE_DIR / slugify(product_keyword)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(product_keyword):
    return product_dir(product_keyword) / "index.json"


def _load_index(product_keyword):
    p = _index_path(product_keyword)
    if not p.exists():
        return {"product_keyword": product_keyword, "items": [], "updated_at": None}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"product_keyword": product_keyword, "items": [], "updated_at": None}


def _save_index(product_keyword, idx):
    idx["product_keyword"] = product_keyword
    idx["updated_at"] = datetime.now().isoformat(timespec="seconds")
    p = _index_path(product_keyword)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, indent=2, default=str), encoding="utf-8")
    tmp.replace(p)


def _http_get(url, headers=None, timeout=TIMEOUT, max_bytes=MAX_BYTES):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"asset too large (>{max_bytes} bytes)")
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return data, ctype


def _ext_from_ctype(ctype, fallback=""):
    m = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    }
    return m.get(ctype, fallback)


def _ext_from_url(url):
    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in IMG_EXT or ext in VID_EXT:
        return ext
    return ""


def _classify(ext, ctype):
    if ext in VID_EXT or ctype.startswith("video/"):
        return "video"
    if ext in IMG_EXT or ctype.startswith("image/"):
        return "image"
    return "other"


def _make_item_id():
    return uuid.uuid4().hex[:12]


def _download_to_folder(folder, url, fname_hint=None):
    """Download url to folder. Returns (local_path, type, ctype, ext)."""
    try:
        data, ctype = _http_get(url, timeout=TIMEOUT)
    except Exception as e:
        raise RuntimeError(f"download failed: {type(e).__name__}: {e}")
    ext = _ext_from_url(url) or _ext_from_ctype(ctype, ".bin")
    typ = _classify(ext, ctype)
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", (fname_hint or "")) or _make_item_id()
    base = os.path.splitext(base)[0][:60] or _make_item_id()
    out = folder / f"{base}{ext}"
    n = 1
    while out.exists():
        out = folder / f"{base}_{n}{ext}"
        n += 1
    out.write_bytes(data)
    return out, typ, ctype, ext


# ---------- per-platform extractors ----------

def _extract_reddit(url):
    """Return [{type, media_url, caption, source_url}] using pullpush.io comments fallback.
    URL example: https://reddit.com/r/<sub>/comments/<id>/<slug>/
    """
    out = []
    try:
        m = re.search(r"/comments/([a-z0-9]+)/", url)
        if not m:
            return out
        post_id = m.group(1)
        # Post body
        api = f"https://api.pullpush.io/reddit/search/submission/?ids={post_id}"
        data, _ = _http_get(api, timeout=15)
        j = json.loads(data.decode("utf-8", "replace"))
        rows = j.get("data") or []
        if rows:
            row = rows[0]
            title = row.get("title") or ""
            selftext = (row.get("selftext") or "")[:600]
            cap = (title + (" - " + selftext if selftext else "")).strip()
            if cap:
                out.append({"type": "text", "media_url": None, "caption": cap, "source_url": url})
            for k in ("url", "url_overridden_by_dest"):
                v = row.get(k)
                if v and isinstance(v, str) and _ext_from_url(v):
                    out.append({"type": _classify(_ext_from_url(v), ""), "media_url": v,
                                "caption": title, "source_url": url})
            # Reddit hosted videos
            media = row.get("media") or {}
            rv = (media.get("reddit_video") or {}).get("fallback_url")
            if rv:
                out.append({"type": "video", "media_url": rv, "caption": title, "source_url": url})
            # Preview images
            preview = (row.get("preview") or {}).get("images") or []
            for im in preview[:2]:
                src = (im.get("source") or {}).get("url")
                if src:
                    src = html.unescape(src)
                    out.append({"type": "image", "media_url": src, "caption": title, "source_url": url})
        # Top 3 comments
        capi = f"https://api.pullpush.io/reddit/search/comment/?link_id={post_id}&sort=score&size=3"
        try:
            cdata, _ = _http_get(capi, timeout=15)
            cj = json.loads(cdata.decode("utf-8", "replace"))
            for c in (cj.get("data") or [])[:3]:
                body = (c.get("body") or "").strip()
                if 10 <= len(body) <= 400:
                    out.append({"type": "text", "media_url": None,
                                "caption": body, "source_url": url})
        except Exception:
            pass
    except Exception as e:
        sys.stderr.write(f"[collateral][reddit] {url}: {e}\n")
    return out


def _extract_youtube(url):
    """Return thumbnail URL (maxresdefault) + title from oEmbed if possible."""
    out = []
    try:
        m = re.search(r"(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{6,15})", url)
        if not m:
            return out
        vid = m.group(1)
        thumb = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
        cap = ""
        try:
            oembed = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
            data, _ = _http_get(oembed, timeout=10)
            j = json.loads(data.decode("utf-8", "replace"))
            cap = j.get("title") or ""
        except Exception:
            pass
        out.append({"type": "image", "media_url": thumb, "caption": cap or "YouTube thumbnail",
                    "source_url": url})
    except Exception as e:
        sys.stderr.write(f"[collateral][youtube] {url}: {e}\n")
    return out


def _extract_pinterest(url):
    """Scrape pin page for the high-res image URL."""
    out = []
    try:
        data, _ = _http_get(url, timeout=20, headers={"Accept-Language": "en-US,en"})
        html_text = data.decode("utf-8", "replace")
        # OG image (canonical for pins)
        m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
        img = m.group(1) if m else None
        if not img:
            m = re.search(r'<meta\s+name=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
            img = m.group(1) if m else None
        if not img:
            m = re.search(r'(https://i\.pinimg\.com/originals/[^"\']+\.(?:jpg|jpeg|png|webp))', html_text, re.I)
            img = m.group(1) if m else None
        title = ""
        tm = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
        if tm: title = html.unescape(tm.group(1))
        if img:
            out.append({"type": "image", "media_url": html.unescape(img),
                        "caption": title or "Pinterest pin", "source_url": url})
    except Exception as e:
        sys.stderr.write(f"[collateral][pinterest] {url}: {e}\n")
    return out


def _extract_generic(url):
    """OG image meta tag scraper for supplier / generic pages."""
    out = []
    try:
        data, _ = _http_get(url, timeout=20, headers={"Accept-Language": "en-US,en"})
        text = data.decode("utf-8", "replace")
        for prop in ("og:image", "twitter:image", "og:image:secure_url"):
            for m in re.finditer(
                rf'<meta\s+(?:property|name)=["\']{re.escape(prop)}["\']\s+content=["\']([^"\']+)["\']',
                text, re.I,
            ):
                img = html.unescape(m.group(1))
                if img.startswith("//"): img = "https:" + img
                if img.startswith("http"):
                    out.append({"type": "image", "media_url": img,
                                "caption": "supplier hero image", "source_url": url})
        # CJ + Aliexpress: also scan for /product/...jpg in raw HTML (a few)
        for m in re.finditer(r'https?://[^\s"\']+?\.(?:jpg|jpeg|png|webp)', text):
            out.append({"type": "image", "media_url": m.group(0),
                        "caption": "supplier image", "source_url": url})
            if len(out) >= 4: break
        # OG title for caption attached to source url
        tm = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', text, re.I)
        if tm:
            title = html.unescape(tm.group(1)).strip()
            if title:
                out.insert(0, {"type": "text", "media_url": None,
                               "caption": title[:300], "source_url": url})
    except Exception as e:
        sys.stderr.write(f"[collateral][generic] {url}: {e}\n")
    # Dedup
    seen = set(); deduped = []
    for o in out:
        key = o.get("media_url") or ("text:" + (o.get("caption") or ""))
        if key in seen: continue
        seen.add(key); deduped.append(o)
    return deduped[:4]


def _detect_platform(url):
    u = (url or "").lower()
    if "reddit.com" in u: return "reddit"
    if "youtube.com" in u or "youtu.be" in u: return "youtube"
    if "pinterest.com" in u or "pin.it" in u: return "pinterest"
    if "cjdropshipping.com" in u: return "cjdropshipping"
    if "aliexpress.com" in u: return "aliexpress"
    return "generic"


def _extract_for(url):
    plat = _detect_platform(url)
    if plat == "reddit": return plat, _extract_reddit(url)
    if plat == "youtube": return plat, _extract_youtube(url)
    if plat == "pinterest": return plat, _extract_pinterest(url)
    return plat, _extract_generic(url)


# ---------- public API ----------

def scrape_product(product_keyword, report):
    """Walk top_social_sources + top_suppliers, download media, index it."""
    with _LOCK:
        folder = product_dir(product_keyword)
        idx = _load_index(product_keyword)
        items = list(idx.get("items") or [])
        seen_urls = {(it.get("source_url"), it.get("type"), it.get("caption_hash"))
                     for it in items}

    social = (report or {}).get("top_social_sources") or []
    supplier = (report or {}).get("top_suppliers") or []
    urls = []
    for s in social:
        if isinstance(s, dict) and s.get("url"):
            urls.append((s.get("url"), s.get("platform") or _detect_platform(s.get("url"))))
    for s in supplier[:6]:  # cap suppliers
        if isinstance(s, dict) and s.get("url"):
            urls.append((s.get("url"), _detect_platform(s.get("url"))))

    added = 0; errors = []
    for src_url, _hint_plat in urls:
        try:
            plat, picks = _extract_for(src_url)
        except Exception as e:
            errors.append({"url": src_url, "error": f"{type(e).__name__}: {e}"})
            continue
        for pick in picks:
            try:
                if pick["type"] == "text":
                    cap = (pick.get("caption") or "").strip()
                    if not cap: continue
                    chash = hashlib.sha1(cap.encode("utf-8")).hexdigest()[:12]
                    key = (src_url, "text", chash)
                    if key in seen_urls: continue
                    seen_urls.add(key)
                    item_id = _make_item_id()
                    items.append({
                        "id": item_id, "type": "text", "filename": None,
                        "local_path": None, "size": len(cap),
                        "source_url": src_url, "source_platform": plat,
                        "caption": cap, "caption_hash": chash,
                        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                    })
                    added += 1
                else:
                    media_url = pick.get("media_url")
                    if not media_url: continue
                    key = (src_url, pick["type"], hashlib.sha1(media_url.encode()).hexdigest()[:12])
                    if key in seen_urls: continue
                    try:
                        local, typ, ctype, ext = _download_to_folder(
                            folder, media_url,
                            fname_hint=f"{plat}_{_make_item_id()}",
                        )
                    except Exception as e:
                        errors.append({"url": media_url, "error": str(e)})
                        continue
                    seen_urls.add(key)
                    item_id = _make_item_id()
                    items.append({
                        "id": item_id, "type": typ,
                        "filename": local.name,
                        "local_path": str(local),
                        "size": local.stat().st_size,
                        "source_url": src_url, "source_platform": plat,
                        "media_url": media_url,
                        "caption": pick.get("caption") or "",
                        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                    })
                    added += 1
            except Exception as e:
                errors.append({"url": pick.get("media_url") or src_url,
                                "error": f"{type(e).__name__}: {e}"})

    with _LOCK:
        idx["items"] = items
        idx["scraped_at"] = datetime.now().isoformat(timespec="seconds")
        idx["errors"] = (idx.get("errors") or [])[-20:] + errors[-20:]
        _save_index(product_keyword, idx)

    return {
        "product_keyword": product_keyword,
        "slug": slugify(product_keyword),
        "folder": str(folder),
        "added": added,
        "total_items": len(items),
        "errors": errors[:10],
        "scraped_at": idx["scraped_at"],
    }


def list_collateral(product_keyword):
    with _LOCK:
        idx = _load_index(product_keyword)
    # Sync size from disk in case files were edited
    folder = product_dir(product_keyword)
    items = []
    total_size = 0
    for it in idx.get("items", []):
        c = dict(it)
        if c.get("local_path"):
            p = pathlib.Path(c["local_path"])
            if p.exists():
                c["size"] = p.stat().st_size
                total_size += c["size"]
            else:
                c["missing"] = True
        items.append(c)
    return {
        "product_keyword": product_keyword,
        "slug": slugify(product_keyword),
        "folder": str(folder),
        "items": items,
        "total_items": len(items),
        "total_size": total_size,
        "scraped_at": idx.get("scraped_at"),
        "updated_at": idx.get("updated_at"),
    }


def add_collateral(product_keyword, source_url=None, uploaded_bytes=None, filename=None):
    folder = product_dir(product_keyword)
    if uploaded_bytes is not None:
        base = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename or "upload") or _make_item_id()
        out = folder / base
        n = 1
        while out.exists():
            stem, ext = os.path.splitext(base)
            out = folder / f"{stem}_{n}{ext}"
            n += 1
        out.write_bytes(uploaded_bytes)
        ext = out.suffix.lower()
        typ = _classify(ext, "")
        item = {
            "id": _make_item_id(), "type": typ, "filename": out.name,
            "local_path": str(out), "size": out.stat().st_size,
            "source_url": None, "source_platform": "upload",
            "caption": filename or out.name,
            "downloaded_at": datetime.now().isoformat(timespec="seconds"),
        }
    elif source_url:
        try:
            local, typ, ctype, ext = _download_to_folder(folder, source_url,
                                                           fname_hint=f"manual_{_make_item_id()}")
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        item = {
            "id": _make_item_id(), "type": typ, "filename": local.name,
            "local_path": str(local), "size": local.stat().st_size,
            "source_url": source_url, "source_platform": _detect_platform(source_url),
            "caption": "", "media_url": source_url,
            "downloaded_at": datetime.now().isoformat(timespec="seconds"),
        }
    else:
        return {"error": "must supply source_url or uploaded_bytes"}
    with _LOCK:
        idx = _load_index(product_keyword)
        idx.setdefault("items", []).append(item)
        _save_index(product_keyword, idx)
    return item


def delete_collateral(product_keyword, item_id):
    with _LOCK:
        idx = _load_index(product_keyword)
        items = idx.get("items", [])
        kept = []; removed = None
        for it in items:
            if it.get("id") == item_id:
                removed = it
            else:
                kept.append(it)
        idx["items"] = kept
        _save_index(product_keyword, idx)
    if removed and removed.get("local_path"):
        try:
            p = pathlib.Path(removed["local_path"])
            if p.exists(): p.unlink()
        except Exception:
            pass
    return {"removed": bool(removed), "remaining": len(kept), "item": removed}


def collateral_paths_for_compose(product_keyword):
    """Return list of (image|video) local paths for use as compose b-roll."""
    idx = _load_index(product_keyword)
    paths = []
    for it in idx.get("items", []):
        if it.get("type") in ("image", "video") and it.get("local_path"):
            p = pathlib.Path(it["local_path"])
            if p.exists():
                paths.append(str(p))
    return paths


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "kitchen"
    # Synthetic test with sample URLs
    report = {
        "top_social_sources": [
            {"platform": "youtube", "url": "https://www.youtube.com/watch?v=cuXyj6OMdJU"},
        ],
        "top_suppliers": [],
    }
    res = scrape_product(kw, report)
    print(json.dumps(res, indent=2, default=str))
