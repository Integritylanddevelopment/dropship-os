#!/usr/bin/env python3
"""
Product Research Tool — Supplier Data Aggregation
==================================================

Fetches product data from multiple suppliers:
- Zendrop API (live — requires ZENDROP_API_KEY in .env)
- AutoDS API (unavailable — returns empty list gracefully)
- AliExpress scraper (live — stdlib scraper, no key needed)

Caches results in local SQLite DB.
Used by ShipStack Engine (/api/research).
"""

import os
import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DROPSHIP_OS_ROOT = Path(__file__).parent
DB_PATH = DROPSHIP_OS_ROOT / "data" / "products.db"
CACHE_TTL_HOURS = 24

# API Keys
ZENDROP_API_KEY = os.getenv("ZENDROP_API_KEY", "")
AUTODS_API_KEY = os.getenv("AUTODS_API_KEY", "")


class ProductDB:
    """SQLite cache for product data."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    supplier TEXT,
                    title TEXT,
                    price REAL,
                    reviews INTEGER,
                    rating REAL,
                    niche TEXT,
                    description TEXT,
                    image_url TEXT,
                    supplier_url TEXT,
                    cached_at TIMESTAMP,
                    UNIQUE(supplier, id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_term TEXT,
                    supplier TEXT,
                    result_count INTEGER,
                    searched_at TIMESTAMP
                )
            """)
            conn.commit()
    
    def add_product(self, product: Dict[str, Any]):
        """Cache a product."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO products
                (id, supplier, title, price, reviews, rating, niche, description, image_url, supplier_url, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product.get("id"),
                product.get("supplier"),
                product.get("title"),
                product.get("price"),
                product.get("reviews", 0),
                product.get("rating", 0.0),
                product.get("niche"),
                product.get("description"),
                product.get("image_url"),
                product.get("supplier_url"),
                datetime.utcnow(),
            ))
            conn.commit()
    
    def get_products(self, search_term: str, supplier: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get cached products matching search.
        Returns only fresh results (< 24 hours old).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)
            
            if supplier:
                rows = conn.execute("""
                    SELECT * FROM products
                    WHERE (title LIKE ? OR niche LIKE ?)
                    AND supplier = ?
                    AND cached_at > ?
                    LIMIT ?
                """, (f"%{search_term}%", f"%{search_term}%", supplier, cutoff, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM products
                    WHERE (title LIKE ? OR niche LIKE ?)
                    AND cached_at > ?
                    LIMIT ?
                """, (f"%{search_term}%", f"%{search_term}%", cutoff, limit)).fetchall()
            
            return [dict(row) for row in rows]


class ProductResearcher:
    """
    Aggregates product data from multiple suppliers.
    """
    
    def __init__(self):
        self.db = ProductDB()
        self.quinn_endpoint = os.getenv("QUINN_ENDPOINT", "http://localhost:8765")
    
    def search_zendrop(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Zendrop API for products matching search_term."""
        import requests as _requests

        if not ZENDROP_API_KEY:
            logger.warning("ZENDROP_API_KEY not set — skipping Zendrop search")
            return []

        try:
            resp = _requests.get(
                "https://api.zendrop.com/v1/search",
                params={"query": search_term, "limit": limit},
                headers={
                    "Authorization": f"Bearer {ZENDROP_API_KEY}",
                    "Accept": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            items = data if isinstance(data, list) else data.get("products", data.get("results", data.get("data", [])))
            results = []
            for it in items[:limit]:
                pid = str(it.get("id") or it.get("product_id") or "")
                if not pid:
                    continue
                results.append({
                    "id": f"zendrop-{pid}",
                    "supplier": "zendrop",
                    "title": it.get("title") or it.get("name") or search_term,
                    "price": float(it.get("price") or it.get("cost") or 0),
                    "reviews": int(it.get("reviews") or it.get("review_count") or 0),
                    "rating": float(it.get("rating") or it.get("star_rating") or 0),
                    "niche": search_term,
                    "description": it.get("description") or "",
                    "image_url": it.get("image_url") or it.get("image") or it.get("thumbnail") or "",
                    "supplier_url": it.get("url") or it.get("supplier_url") or f"https://zendrop.com/products/{pid}",
                })
            return results
        except Exception as exc:
            logger.error(f"Zendrop API error for '{search_term}': {exc}")
            return []
    
    def search_autods(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search AutoDS API.
        No API key available — returns empty list so the pipeline continues gracefully.
        """
        logger.info("AutoDS API key not available — returning empty results")
        return []
    
    def search_aliexpress(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """MVP AliExpress scraper. Stdlib, no API key. Returns [] on any failure so pipeline keeps moving."""
        import urllib.request, urllib.parse, re
        import http.cookiejar as _cj
        import json as _json
        try:
            slug = urllib.parse.quote(search_term.replace(" ", "-"))
            url = f"https://www.aliexpress.com/w/wholesale-{slug}.html"
            jar = _cj.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPRedirectHandler())
            opener.addheaders = [
                ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"),
                ("Accept-Language", "en-US,en;q=0.9"),
                ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9"),
            ]
            with opener.open(url, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            m = re.search(r"window\._dida_config_\s*=\s*({.+?});", html, re.DOTALL)
            items = []
            if m:
                try:
                    blob = _json.loads(m.group(1))
                    items = blob.get("data", {}).get("root", {}).get("fields", {}).get("mods", {}).get("itemList", {}).get("content", []) or []
                except Exception:
                    items = []
            results = []
            for it in items[:limit]:
                pid = str(it.get("productId") or it.get("itemId") or "")
                if not pid:
                    continue
                price_obj = it.get("prices", {}).get("salePrice", {}) if isinstance(it.get("prices"), dict) else {}
                price_str = price_obj.get("minPrice") or price_obj.get("formattedPrice") or "0"
                try:
                    price = float(re.sub(r"[^\d.]", "", str(price_str)) or 0)
                except Exception:
                    price = 0.0
                title_obj = it.get("title") if isinstance(it.get("title"), dict) else {}
                results.append({
                    "id": f"aliexpress-{pid}",
                    "supplier": "aliexpress",
                    "title": title_obj.get("displayTitle", search_term),
                    "price": price,
                    "reviews": (it.get("trade") or {}).get("realTradeCount") or 0,
                    "rating": float((it.get("evaluation") or {}).get("starRating", 0) or 0),
                    "niche": search_term,
                    "description": "AliExpress product (MVP scrape)",
                    "image_url": (it.get("image") or {}).get("imgUrl", ""),
                    "supplier_url": f"https://www.aliexpress.us/item/{pid}.html",
                })
            return results
        except Exception as exc:
            try:
                from loguru import logger
                logger.warning(f"AliExpress MVP scraper returned no results for '{search_term}': {exc}")
            except Exception:
                pass
            return []

    def _aliexpress_gate_old(self, search_term: str, limit: int = 20):
        """Old NotImplementedError gate, kept for reference."""
        raise NotImplementedError(
            "AliExpress scraper not wired — implement Selenium/BeautifulSoup scraper or use AliExpress API. "
            "See Directive #19. This is a deliberate gate to prevent deployment with stub data."
        )

        # TODO: Use Selenium + BeautifulSoup or AliExpress API
        # Fetch first N results for search_term
        # Then return real results instead of placeholder below

        # Placeholder results (never reached due to gate above)
        return [
            {
                "id": "aliexpress-789",
                "supplier": "aliexpress",
                "title": f"{search_term} from AliExpress",
                "price": 3.50,
                "reviews": 500,
                "rating": 4.3,
                "niche": search_term,
                "description": "Budget option with high volume",
                "image_url": "https://example.com/image.jpg",
                "supplier_url": "https://aliexpress.com/item/789",
            }
        ]
    
    def research(self, search_term: str, suppliers: List[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Research products across suppliers.
        
        Args:
            search_term: Product name or niche
            suppliers: ["zendrop", "autods", "aliexpress"] or None for all
            limit: Results per supplier
        
        Returns:
            Combined list of products (deduplicated)
        """
        if suppliers is None:
            suppliers = ["zendrop", "autods", "aliexpress"]
        
        products = []
        seen_ids = set()
        
        for supplier in suppliers:
            try:
                if supplier == "zendrop":
                    results = self.search_zendrop(search_term, limit)
                elif supplier == "autods":
                    results = self.search_autods(search_term, limit)
                elif supplier == "aliexpress":
                    results = self.search_aliexpress(search_term, limit)
                else:
                    continue
                
                for product in results:
                    # Deduplicate by ID
                    if product["id"] not in seen_ids:
                        seen_ids.add(product["id"])
                        self.db.add_product(product)
                        products.append(product)
            except Exception as e:
                logger.error(f"Error searching {supplier}: {e}")
        
        return products[:limit]


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    researcher = ProductResearcher()
    
    print("\n=== Product Research Test ===\n")
    
    results = researcher.research("pet collars", suppliers=["zendrop", "autods", "aliexpress"], limit=5)
    print(f"Found {len(results)} products:\n")
    
    for product in results:
        print(f"  {product['title']} (${product['price']:.2f})")
        print(f"    Reviews: {product['reviews']} | Rating: {product['rating']}")
        print(f"    Supplier: {product['supplier']}")
        print()
