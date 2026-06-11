"""Spocket public catalog browse - the search-products endpoint is public read-only
for basic catalog data. We do NOT log in. If Spocket gates this without auth,
fail open and return []."""
import urllib.parse
from .. signals import _common

def search(keyword: str, limit: int = 20) -> list[dict]:
    url = f"https://www.spocket.co/products?search={urllib.parse.quote(keyword)}&page=1&per_page={limit}"
    data = _common.fetch_json(url, timeout=20, headers={
        "Accept": "application/json",
        "Referer": "https://www.spocket.co/",
    })
    if not data:
        return []
    items = data.get("products") or data.get("data") or []
    out = []
    for p in items:
        out.append({
            "supplier": "spocket",
            "supplier_url": f"https://www.spocket.co/products/{p.get('id','')}",
            "id": p.get("id"),
            "title": p.get("title") or p.get("name") or "",
            "image": (p.get("images") or [""])[0] if isinstance(p.get("images"), list) else "",
            "unit_cost": float(p.get("price") or 0),
            "retail_price_suggested": float(p.get("retail_price") or 0),
            "moq": 1,
            "shipping_options": [p.get("ship_from") or "Unknown"],
            "dropship_available": True,
            "blind_dropship": False,
            "categories": p.get("category") or "",
            "raw": p,
        })
    return out