"""CJdropshipping supplier search via official API.

Auth flow:
  POST /api2.0/v1/authentication/getAccessToken with {apiKey} -> accessToken (15d TTL)
  Cache token locally; refresh on 1600x auth errors.
Search:
  GET /api2.0/v1/product/list?pageNum=&pageSize=&productNameEn= with CJ-Access-Token header
"""
import os, json, time, pathlib, urllib.parse, urllib.request

BASE = "https://developers.cjdropshipping.com/api2.0/v1"
CACHE = pathlib.Path(__file__).parent / ".cj_token.json"

def _load_key():
    key = os.environ.get("CJ_API_KEY")
    if key:
        return key
    # Fall back to .env file alongside project root
    here = pathlib.Path(__file__).resolve()
    for p in [here.parent.parent.parent / ".env", here.parents[3] / ".env"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("CJ_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""

def _http_json(url, method="GET", body=None, headers=None, timeout=20):
    hdr = {"Accept": "application/json"}
    if headers: hdr.update(headers)
    data = None
    if body is not None:
        hdr["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        try:
            err = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            return json.loads(err) if err.startswith("{") else {"_exception": str(e), "_body": err[:300]}
        except Exception:
            return {"_exception": str(e)}

def _get_token(force=False):
    if not force and CACHE.exists():
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if cached.get("expires", 0) > time.time() + 60 and cached.get("accessToken"):
                return cached["accessToken"]
        except Exception:
            pass
    key = _load_key()
    if not key:
        return ""
    resp = _http_json(f"{BASE}/authentication/getAccessToken", method="POST", body={"apiKey": key})
    if resp.get("success") or resp.get("result"):
        tok = (resp.get("data") or {}).get("accessToken", "")
        try:
            CACHE.write_text(json.dumps({
                "accessToken": tok,
                "expires": time.time() + 14 * 86400,  # 15d default, keep 1d buffer
            }), encoding="utf-8")
        except Exception:
            pass
        return tok
    return ""

def search(keyword: str, limit: int = 15) -> list:
    tok = _get_token()
    if not tok:
        return []
    url = (
        f"{BASE}/product/list?pageNum=1&pageSize={limit}"
        f"&productNameEn={urllib.parse.quote(keyword)}"
    )
    resp = _http_json(url, headers={"CJ-Access-Token": tok}, timeout=25)
    # Refresh once on auth failure
    if str(resp.get("code", "")).startswith("160") and not resp.get("success"):
        tok = _get_token(force=True)
        if tok:
            resp = _http_json(url, headers={"CJ-Access-Token": tok}, timeout=25)
    items = ((resp.get("data") or {}).get("list")) or []
    out = []
    for p in items:
        try:
            unit_cost = float(p.get("sellPrice") or p.get("productPrice") or 0)
        except Exception:
            unit_cost = 0.0
        pid = p.get("productId") or p.get("pid") or ""
        out.append({
            "supplier": "cjdropshipping",
            "supplier_url": f"https://www.cjdropshipping.com/product/{pid}.html",
            "id": pid,
            "title": p.get("productNameEn") or p.get("productName") or "",
            "image": p.get("productImage") or p.get("productImg") or "",
            "unit_cost": unit_cost,
            "moq": int(p.get("minOrderQuantity") or 1),
            "shipping_options": ["CJPacket", "ePacket", "DHL", "FedEx"],
            "supplier_rating": float(p.get("productScore") or 0),
            "review_count": int(p.get("evalAverage") or 0),
            "dropship_available": True,
            "blind_dropship": True,
            "categories": p.get("categoryName") or p.get("categoryFullName") or "",
            "raw": p,
        })
    return out