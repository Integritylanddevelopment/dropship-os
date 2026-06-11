#!/usr/bin/env python3
"""
integrations/aliexpress_connector.py — AliExpress Dropshipping Connector
=========================================================================
ShipStack production connector for AliExpress Open Platform API.

Capabilities:
  - Product search with ShipStack scoring (margin × rating × volume × shipping)
  - Full product detail (variants, images, shipping options)
  - Dropshipping order placement (requires DS API access from AliExpress)
  - Order tracking + logistics detail
  - Shipping cost estimation
  - OAuth2 flow for order-level access
  - Bulk niche scanner for the Decision Engine

ENV VARS REQUIRED (set in .env):
  ALIEXPRESS_APP_KEY      — from AliExpress Open Platform
  ALIEXPRESS_APP_SECRET   — from AliExpress Open Platform
  ALIEXPRESS_ACCESS_TOKEN — from OAuth flow (required for order placement only)

Register: https://developers.aliexpress.com
Apply for: Dropship API (not affiliate-only)
"""

import hashlib
import json
import math
import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

GATEWAY_PRIMARY = "https://api-sg.aliexpress.com/sync"
GATEWAY_FALLBACK = "https://api.aliexpress.com/sync"


# ══════════════════════════════════════════════════════════════
# SIGNATURE ENGINE
# ══════════════════════════════════════════════════════════════

def _sign(app_secret: str, params: dict) -> str:
    """HMAC-MD5 signature per AliExpress spec."""
    sorted_params = sorted(params.items())
    base = app_secret + "".join(f"{k}{v}" for k, v in sorted_params) + app_secret
    return hashlib.md5(base.encode("utf-8")).hexdigest().upper()


def _build_payload(method: str, app_key: str, app_secret: str, extra: dict) -> dict:
    params = {
        "method": method,
        "app_key": app_key,
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        **extra,
    }
    params["sign"] = _sign(app_secret, params)
    return params


# ══════════════════════════════════════════════════════════════
# MAIN CONNECTOR
# ══════════════════════════════════════════════════════════════

class AliExpressConnector:

    SCORE_WEIGHTS = {
        "margin":   0.45,
        "rating":   0.25,
        "orders":   0.20,
        "shipping": 0.10,
    }

    def __init__(self):
        self.app_key      = os.getenv("ALIEXPRESS_APP_KEY", "").strip()
        self.app_secret   = os.getenv("ALIEXPRESS_APP_SECRET", "").strip()
        self.access_token = os.getenv("ALIEXPRESS_ACCESS_TOKEN", "").strip()
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        self._assert_configured()

    def _assert_configured(self):
        missing = []
        if not self.app_key:    missing.append("ALIEXPRESS_APP_KEY")
        if not self.app_secret: missing.append("ALIEXPRESS_APP_SECRET")
        if missing:
            raise EnvironmentError(
                f"[AliExpress] Missing required env vars: {', '.join(missing)}\n"
                f"Set them in: {BASE_DIR / '.env'}\n"
                f"Get credentials at: https://developers.aliexpress.com"
            )

    # ── Product Search ────────────────────────────────────────

    def search_products(
        self,
        keyword: str,
        target_sell_price: float = 0.0,
        min_margin_pct: float = 50.0,
        min_rating: float = 4.0,
        min_orders: int = 100,
        limit: int = 30,
        sort: str = "LAST_VOLUME_DESC",
        ship_to: str = "US",
    ) -> list:
        """
        Search AliExpress and return ShipStack-scored, filtered products.

        sort options: LAST_VOLUME_DESC | SALE_PRICE_ASC | SALE_PRICE_DESC
        """
        params = {
            "keywords": keyword,
            "sort": sort,
            "page_size": "50",
            "page_no": "1",
            "ship_to_country": ship_to,
            "currency": "USD",
            "language": "en",
        }

        raw = self._call("aliexpress.affiliate.product.query", params)

        products_raw = (
            raw.get("aliexpress_affiliate_product_query_response", {})
               .get("resp_result", {})
               .get("result", {})
               .get("products", {})
               .get("product", [])
        )

        results = []
        for p in products_raw:
            scored = self._score(p, target_sell_price)
            if scored is None:
                continue
            if scored["margin_pct"] < min_margin_pct:
                continue
            if scored["rating"] < min_rating:
                continue
            if scored["order_count"] < min_orders:
                continue
            results.append(scored)

        results.sort(key=lambda x: x["shipstack_score"], reverse=True)
        return results[:limit]

    def _score(self, raw: dict, target_sell_price: float) -> Optional[dict]:
        try:
            product_id   = str(raw.get("product_id", ""))
            title        = raw.get("product_title", "")
            cost_price   = float(raw.get("target_sale_price", 0) or raw.get("sale_price", 0))
            orig_price   = float(raw.get("target_original_price", cost_price))
            rating_pct   = raw.get("evaluate_rate", "0").replace("%", "")
            rating       = float(rating_pct) / 20  # percent → 5-star
            order_count  = int(raw.get("lastest_volume", 0))
            image_url    = raw.get("product_main_image_url", "")
            product_url  = raw.get("product_detail_url", "")
            commission   = float(raw.get("commission_rate", "0").replace("%", ""))
            shop_url     = raw.get("shop_url", "")
            free_ship    = raw.get("freeship_min_day", 1) == 0

            if cost_price <= 0:
                return None

            sell_price  = target_sell_price if target_sell_price > 0 else round(cost_price * 3, 2)
            margin_usd  = sell_price - cost_price
            margin_pct  = (margin_usd / sell_price) * 100 if sell_price > 0 else 0

            margin_score   = min(margin_pct / 80, 1.0)
            rating_score   = rating / 5.0
            order_score    = min(math.log10(max(order_count, 1)) / 4, 1.0)
            shipping_score = 1.0 if free_ship else 0.5

            score = round(
                margin_score   * self.SCORE_WEIGHTS["margin"] +
                rating_score   * self.SCORE_WEIGHTS["rating"] +
                order_score    * self.SCORE_WEIGHTS["orders"] +
                shipping_score * self.SCORE_WEIGHTS["shipping"],
                4
            )

            return {
                "product_id":      product_id,
                "title":           title,
                "cost_price":      round(cost_price, 2),
                "sell_price":      round(sell_price, 2),
                "margin_usd":      round(margin_usd, 2),
                "margin_pct":      round(margin_pct, 1),
                "original_price":  round(orig_price, 2),
                "commission_rate": commission,
                "rating":          round(rating, 2),
                "order_count":     order_count,
                "free_shipping":   free_ship,
                "image_url":       image_url,
                "product_url":     product_url,
                "shop_url":        shop_url,
                "shipstack_score": score,
                "sourced_at":      datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"[AliExpress] Scoring error: {e}")
            return None

    # ── Product Detail ────────────────────────────────────────

    def get_product_detail(self, product_id: str, ship_to: str = "US") -> dict:
        """Full product detail: variants, images, shipping."""
        raw = self._call("aliexpress.affiliate.productdetail.get", {
            "product_ids": product_id,
            "ship_to_country": ship_to,
            "currency": "USD",
            "language": "en",
        })
        result = (
            raw.get("aliexpress_affiliate_productdetail_get_response", {})
               .get("resp_result", {})
               .get("result", {})
               .get("products", {})
               .get("product", [{}])
        )
        return result[0] if result else {}

    # ── Order Placement ───────────────────────────────────────

    def place_order(
        self,
        product_id: str,
        sku_id: str,
        quantity: int,
        shipping_address: dict,
        logistics_service: str = "CAINIAO_STANDARD",
    ) -> dict:
        """
        Place a dropshipping order on AliExpress.
        Requires DS API approval + ALIEXPRESS_ACCESS_TOKEN in .env.

        logistics_service options:
          CAINIAO_STANDARD  — AliExpress Standard (~15-30 days, usually free)
          CAINIAO_ECONOMY   — slower, cheapest
          UPS / DHL / FEDEX — faster, costs more

        shipping_address keys:
          name, address1, address2, city, state, zip, country, phone, email
        """
        if not self.access_token:
            raise EnvironmentError(
                "[AliExpress] ALIEXPRESS_ACCESS_TOKEN required for order placement.\n"
                f"Run OAuth flow: python aliexpress_connector.py oauth"
            )

        product_items = json.dumps([{
            "product_id":    product_id,
            "product_count": quantity,
            "sku_attr":      sku_id,
        }])

        logistics_address = json.dumps({
            "contact_person": shipping_address.get("name", ""),
            "address":        shipping_address.get("address1", ""),
            "address2":       shipping_address.get("address2", ""),
            "city":           shipping_address.get("city", ""),
            "province":       shipping_address.get("state", ""),
            "zip":            shipping_address.get("zip", ""),
            "country":        shipping_address.get("country", "US"),
            "phone_country":  "+1",
            "mobile_no":      shipping_address.get("phone", ""),
            "email":          shipping_address.get("email", ""),
        })

        raw = self._call("aliexpress.ds.order.create", {
            "product_items":        product_items,
            "logistics_address":    logistics_address,
            "logistics_service_name": logistics_service,
            "access_token":         self.access_token,
        })

        result   = raw.get("aliexpress_ds_order_create_response", {}).get("result", {})
        order_id = result.get("order_id", "")

        if order_id:
            print(f"[AliExpress] ✅ Order {order_id} placed for {shipping_address.get('name')}")
            self._log_order(order_id, product_id, shipping_address)
        else:
            print(f"[AliExpress] ❌ Order failed: {result}")

        return result

    # ── Tracking ──────────────────────────────────────────────

    def get_order_status(self, order_id: str) -> dict:
        raw = self._call("aliexpress.trade.order.get", {"order_id": order_id})
        return raw.get("aliexpress_trade_order_get_response", {}).get("order_info", {})

    def get_tracking(self, order_id: str) -> dict:
        raw = self._call("aliexpress.logistics.order.detail.get", {"order_id": order_id})
        lg  = raw.get("aliexpress_logistics_order_detail_get_response", {})
        return {
            "order_id":           order_id,
            "tracking_number":    lg.get("logistics_no", ""),
            "carrier":            lg.get("logistics_name", ""),
            "status":             lg.get("order_status", ""),
            "estimated_delivery": lg.get("estimated_delivery_time", ""),
        }

    # ── Shipping Estimate ─────────────────────────────────────

    def estimate_shipping(self, product_id: str, quantity: int = 1, ship_to: str = "US") -> list:
        raw = self._call("aliexpress.logistics.buyer.freight.calculate", {
            "product_id":             product_id,
            "product_num":            quantity,
            "send_goods_country_code": "CN",
            "receive_country_code":   ship_to,
        })
        freights = (
            raw.get("aliexpress_logistics_buyer_freight_calculate_response", {})
               .get("result", {})
               .get("freight", {})
               .get("freight", [])
        )
        return [
            {
                "service":  f.get("logistics_service_name", ""),
                "cost":     float(f.get("freight", {}).get("amount", 0)),
                "currency": f.get("freight", {}).get("currency", "USD"),
                "min_days": f.get("min_delivery_days", 0),
                "max_days": f.get("max_delivery_days", 0),
                "tracking": f.get("tracking_available", False),
            }
            for f in freights
        ]

    # ── OAuth ─────────────────────────────────────────────────

    def get_oauth_url(
        self,
        redirect_uri: str = "https://dropship-os-hazel.vercel.app/auth/aliexpress"
    ) -> str:
        """Step 1 of OAuth — generate authorization URL."""
        return (
            f"https://oauth.aliexpress.com/authorize"
            f"?response_type=code"
            f"&client_id={self.app_key}"
            f"&redirect_uri={redirect_uri}"
            f"&state=shipstack"
            f"&view=web"
        )

    def complete_oauth(
        self,
        auth_code: str,
        redirect_uri: str = "https://dropship-os-hazel.vercel.app/auth/aliexpress"
    ) -> dict:
        """Step 2 of OAuth — exchange code for access token, then save to .env."""
        resp = requests.post(
            "https://oauth.aliexpress.com/token",
            data={
                "grant_type":    "authorization_code",
                "code":          auth_code,
                "client_id":     self.app_key,
                "client_secret": self.app_secret,
                "redirect_uri":  redirect_uri,
            },
            timeout=15,
        )
        result = resp.json()

        if "access_token" in result:
            token   = result["access_token"]
            expires = result.get("expire_time", "unknown")
            # Write directly into .env
            env_path = BASE_DIR / ".env"
            env_text = env_path.read_text(encoding="utf-8")
            if "ALIEXPRESS_ACCESS_TOKEN=" in env_text:
                lines = env_text.splitlines()
                lines = [
                    f"ALIEXPRESS_ACCESS_TOKEN={token}" if l.startswith("ALIEXPRESS_ACCESS_TOKEN=") else l
                    for l in lines
                ]
                env_path.write_text("\n".join(lines), encoding="utf-8")
            else:
                env_path.write_text(
                    env_text.rstrip() + f"\nALIEXPRESS_ACCESS_TOKEN={token}\n",
                    encoding="utf-8",
                )
            print(f"[AliExpress] ✅ Access token saved to .env (expires in {expires}s)")
        else:
            print(f"[AliExpress] ❌ OAuth failed: {result}")

        return result

    # ── Internal ──────────────────────────────────────────────

    def _call(self, method: str, extra: dict) -> dict:
        payload = _build_payload(method, self.app_key, self.app_secret, extra)
        for gateway in [GATEWAY_PRIMARY, GATEWAY_FALLBACK]:
            try:
                resp = self.session.post(gateway, data=payload, timeout=15)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                print(f"[AliExpress] Timeout on {gateway}, trying next...")
            except Exception as e:
                print(f"[AliExpress] Error on {gateway}: {e}")
        raise RuntimeError(f"[AliExpress] All gateways failed for method: {method}")

    def _log_order(self, order_id: str, product_id: str, address: dict):
        log_path = BASE_DIR / "data" / "aliexpress_orders.json"
        log_path.parent.mkdir(exist_ok=True)
        orders = json.loads(log_path.read_text()) if log_path.exists() else []
        orders.append({
            "order_id":   order_id,
            "product_id": product_id,
            "customer":   address.get("name", ""),
            "placed_at":  datetime.utcnow().isoformat(),
        })
        log_path.write_text(json.dumps(orders, indent=2))


# ══════════════════════════════════════════════════════════════
# BULK NICHE SCANNER — for Decision Engine daily runs
# ══════════════════════════════════════════════════════════════

class AliExpressScanner:
    """Scans target niches daily, saves top products for Decision Engine."""

    TARGET_NICHES = [
        {"keyword": "posture corrector",       "sell_price": 29.99},
        {"keyword": "pet accessories cat toy",  "sell_price": 19.99},
        {"keyword": "kitchen gadgets",          "sell_price": 24.99},
        {"keyword": "fitness resistance bands", "sell_price": 34.99},
        {"keyword": "led strip lights bedroom", "sell_price": 22.99},
        {"keyword": "phone holder car mount",   "sell_price": 19.99},
        {"keyword": "portable blender",         "sell_price": 39.99},
        {"keyword": "bamboo cutting board",     "sell_price": 27.99},
    ]

    def __init__(self):
        self.connector   = AliExpressConnector()
        self.output_path = BASE_DIR / "data" / "aliexpress_top_products.json"

    def scan_all(self, min_margin: float = 55.0, min_rating: float = 4.2) -> dict:
        print(f"\n[AliExpress Scanner] Scanning {len(self.TARGET_NICHES)} niches...")
        all_results   = {}
        total_found   = 0

        for niche in self.TARGET_NICHES:
            keyword    = niche["keyword"]
            sell_price = niche["sell_price"]
            print(f"  → {keyword} (sell @ ${sell_price})")

            products = self.connector.search_products(
                keyword=keyword,
                target_sell_price=sell_price,
                min_margin_pct=min_margin,
                min_rating=min_rating,
                limit=10,
            )

            all_results[keyword] = {
                "sell_price":    sell_price,
                "product_count": len(products),
                "top_products":  products[:5],
                "best_score":    products[0]["shipstack_score"] if products else 0,
                "best_margin":   products[0]["margin_pct"] if products else 0,
                "scanned_at":    datetime.utcnow().isoformat(),
            }
            total_found += len(products)
            print(f"     {len(products)} qualifying products")

        self.output_path.parent.mkdir(exist_ok=True)
        self.output_path.write_text(json.dumps(all_results, indent=2))

        winners = sorted(
            [(k, v) for k, v in all_results.items() if v["product_count"] > 0],
            key=lambda x: x[1]["best_score"],
            reverse=True,
        )

        return {
            "scan_completed":      datetime.utcnow().isoformat(),
            "total_products_found": total_found,
            "top_3_niches": [
                {"niche": k, "best_margin": v["best_margin"], "score": v["best_score"]}
                for k, v in winners[:3]
            ],
            "all_results": all_results,
        }

    def get_top_products(self, top_n: int = 10) -> list:
        if not self.output_path.exists():
            return []
        data = json.loads(self.output_path.read_text())
        all_products = []
        for niche_data in data.values():
            all_products.extend(niche_data.get("top_products", []))
        all_products.sort(key=lambda x: x.get("shipstack_score", 0), reverse=True)
        return all_products[:top_n]


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        ax = AliExpressConnector()
        print(f"  App Key:  {ax.app_key[:6]}...")
        print(f"  Token:    {'SET' if ax.access_token else 'NOT SET (needed for orders)'}")
        print(f"  Gateway:  {GATEWAY_PRIMARY}")

    elif cmd == "search" and len(sys.argv) > 2:
        keyword = " ".join(sys.argv[2:])
        ax      = AliExpressConnector()
        results = ax.search_products(keyword, target_sell_price=29.99, limit=5)
        for r in results:
            print(f"\n[{r['shipstack_score']:.2f}] {r['title']}")
            print(f"  Cost: ${r['cost_price']} | Sell: ${r['sell_price']} | Margin: {r['margin_pct']}%")
            print(f"  Rating: {r['rating']} | Orders: {r['order_count']} | Free ship: {r['free_shipping']}")

    elif cmd == "scan":
        scanner = AliExpressScanner()
        summary = scanner.scan_all()
        for n in summary["top_3_niches"]:
            print(f"  {n['niche']}: {n['best_margin']}% margin | score {n['score']:.2f}")

    elif cmd == "oauth":
        ax = AliExpressConnector()
        print("\nVisit this URL to authorize order-level access:")
        print(ax.get_oauth_url())
        code = input("\nPaste the auth code here: ").strip()
        if code:
            ax.complete_oauth(code)

    elif cmd == "track" and len(sys.argv) > 2:
        ax = AliExpressConnector()
        print(ax.get_tracking(sys.argv[2]))

    else:
        print("Usage:")
        print("  python aliexpress_connector.py status")
        print("  python aliexpress_connector.py search <keyword>")
        print("  python aliexpress_connector.py scan")
        print("  python aliexpress_connector.py oauth")
        print("  python aliexpress_connector.py track <order_id>")
