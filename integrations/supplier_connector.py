#!/usr/bin/env python3
"""
integrations/supplier_connector.py — Dropship Supplier Connector
Connects to Zendrop, AutoDS, and AliExpress to:
- Find products
- Place orders automatically when a Stripe payment comes in
- Track order status
- Get tracking numbers

Requires: ZENDROP_API_KEY, AUTODS_API_KEY in .env
"""

import json
import os
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


# ══════════════════════════════════════════════
# ZENDROP
# ══════════════════════════════════════════════

class ZendropConnector:
    """
    Zendrop API — AI store builder + automated fulfillment.
    Docs: https://app.zendrop.com/api-docs
    Requires: ZENDROP_API_KEY
    """
    BASE_URL = "https://app.zendrop.com/api/v1"

    def __init__(self):
        self.api_key = os.getenv("ZENDROP_API_KEY", "")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_products(self, query: str, limit: int = 20) -> list:
        if not self.is_configured():
            return []
        resp = requests.get(f"{self.BASE_URL}/products", headers=self.headers,
                            params={"search": query, "limit": limit})
        return resp.json().get("data", [])

    def place_order(self, product_id: str, variant_id: str, shipping_address: dict, quantity: int = 1) -> dict:
        """
        Place a dropship order after a Stripe payment.
        shipping_address: {name, address1, city, state, zip, country, email, phone}
        """
        if not self.is_configured():
            return {"error": "ZENDROP_API_KEY not set"}
        payload = {
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity": quantity,
            "shipping_address": shipping_address,
        }
        resp = requests.post(f"{self.BASE_URL}/orders", headers=self.headers, json=payload)
        result = resp.json()
        if resp.status_code in [200, 201]:
            print(f"[Zendrop] ✅ Order placed: {result.get('order_id')} — {shipping_address.get('name')}")
        else:
            print(f"[Zendrop] ❌ Order error: {result}")
        return result

    def get_order_status(self, order_id: str) -> dict:
        if not self.is_configured():
            return {}
        resp = requests.get(f"{self.BASE_URL}/orders/{order_id}", headers=self.headers)
        return resp.json()


# ══════════════════════════════════════════════
# AUTODS
# ══════════════════════════════════════════════

class AutoDSConnector:
    """
    AutoDS API — product import + automatic order fulfillment.
    Docs: https://autods.com/api-docs
    Requires: AUTODS_API_KEY
    """
    BASE_URL = "https://app.autods.com/api/v1"

    def __init__(self):
        self.api_key = os.getenv("AUTODS_API_KEY", "")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_products(self, query: str, limit: int = 20, min_margin: float = 50.0) -> list:
        if not self.is_configured():
            return []
        resp = requests.get(f"{self.BASE_URL}/products/search", headers=self.headers,
                            params={"q": query, "limit": limit})
        products = resp.json().get("products", [])
        # Filter by margin
        filtered = []
        for p in products:
            cost = float(p.get("cost_price", 0))
            sell = float(p.get("sell_price", cost * 2))
            margin = (sell - cost) / sell * 100 if sell > 0 else 0
            if margin >= min_margin:
                p["margin_pct"] = round(margin, 1)
                filtered.append(p)
        return sorted(filtered, key=lambda x: x.get("margin_pct", 0), reverse=True)

    def place_order(self, product_id: str, shipping_address: dict) -> dict:
        if not self.is_configured():
            return {"error": "AUTODS_API_KEY not set"}
        payload = {"product_id": product_id, "shipping_address": shipping_address}
        resp = requests.post(f"{self.BASE_URL}/orders", headers=self.headers, json=payload)
        return resp.json()

    def get_tracking(self, order_id: str) -> dict:
        if not self.is_configured():
            return {}
        resp = requests.get(f"{self.BASE_URL}/orders/{order_id}/tracking", headers=self.headers)
        return resp.json()


# ══════════════════════════════════════════════
# ORDER MONITOR — Stripe → Supplier
# ══════════════════════════════════════════════

class OrderMonitor:
    """
    Monitors Stripe for new payments → automatically places
    supplier orders via Zendrop or AutoDS.

    Matching strategy (most → least reliable):
      1. Checkout session payment_link ID → stripe_links.json → product name
      2. Checkout session line item name → product_supplier_map.json
      3. Charge description → product_supplier_map.json (legacy fallback)
    """

    def __init__(self):
        self.zendrop = ZendropConnector()
        self.autods = AutoDSConnector()
        self.processed_path = BASE_DIR / "data" / "processed_orders.json"
        self._load_processed()

    def _load_processed(self):
        if self.processed_path.exists():
            self.processed = set(json.loads(self.processed_path.read_text()))
        else:
            self.processed = set()

    def _save_processed(self):
        self.processed_path.parent.mkdir(exist_ok=True)
        self.processed_path.write_text(json.dumps(list(self.processed), indent=2))

    def poll(self) -> list:
        """
        Check Stripe for new paid checkout sessions and place supplier orders.
        Returns list of orders placed this cycle.
        """
        try:
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        except ImportError:
            print("[OrderMonitor] stripe library not installed")
            return []

        orders_placed = []
        product_map = self._load_product_map()
        link_map = self._load_link_map()

        # ── Primary: checkout sessions (covers all payment link purchases) ──
        try:
            sessions = stripe.checkout.Session.list(limit=20)
            for session in sessions.data:
                if session.payment_status != "paid":
                    continue
                session_key = f"cs_{session.id}"
                if session_key in self.processed:
                    continue

                print(f"[OrderMonitor] New session: {session.id} — ${session.amount_total / 100:.2f}")

                shipping = self._extract_session_shipping(session)
                if not shipping:
                    print(f"[OrderMonitor] No shipping for {session.id} — manual fulfillment needed")
                    self.processed.add(session_key)
                    continue

                # Match product: payment_link ID first, then line item name
                product_name = link_map.get(session.payment_link or "", "")
                if not product_name:
                    try:
                        items = stripe.checkout.Session.list_line_items(session.id, limit=1)
                        if items.data:
                            product_name = items.data[0].description or ""
                    except Exception:
                        pass

                supplier_product = product_map.get(product_name, {})
                order_result = self._fulfill(supplier_product, product_name, shipping)

                order_log = {
                    "stripe_session_id": session.id,
                    "stripe_payment_link": session.payment_link,
                    "amount_usd": session.amount_total / 100,
                    "product": product_name,
                    "customer": shipping.get("name"),
                    "supplier_result": order_result,
                    "processed_at": datetime.utcnow().isoformat(),
                }
                self._log_order(order_log)
                self.processed.add(session_key)
                orders_placed.append(order_log)

        except Exception as e:
            print(f"[OrderMonitor] Session poll error: {e}")

        # ── Fallback: charges (covers direct payment intents not from links) ──
        try:
            charges = stripe.Charge.list(limit=20)
            for charge in charges.data:
                if charge.status != "succeeded":
                    continue
                if charge.id in self.processed:
                    continue

                print(f"[OrderMonitor] New charge: {charge.id} — ${charge.amount / 100:.2f}")

                shipping = self._extract_shipping(charge)
                if not shipping:
                    print(f"[OrderMonitor] No shipping for {charge.id} — manual fulfillment needed")
                    self.processed.add(charge.id)
                    continue

                product_name = charge.description or ""
                supplier_product = product_map.get(product_name, {})
                order_result = self._fulfill(supplier_product, product_name, shipping)

                order_log = {
                    "stripe_charge_id": charge.id,
                    "amount_usd": charge.amount / 100,
                    "product": product_name,
                    "customer": shipping.get("name"),
                    "supplier_result": order_result,
                    "processed_at": datetime.utcnow().isoformat(),
                }
                self._log_order(order_log)
                self.processed.add(charge.id)
                orders_placed.append(order_log)

        except Exception as e:
            print(f"[OrderMonitor] Charge poll error: {e}")

        self._save_processed()
        return orders_placed

    def _fulfill(self, supplier_product: dict, product_name: str, shipping: dict) -> dict:
        """Place order with the appropriate supplier."""
        if supplier_product.get("supplier") == "zendrop" and self.zendrop.is_configured():
            return self.zendrop.place_order(
                product_id=supplier_product["product_id"],
                variant_id=supplier_product.get("variant_id", ""),
                shipping_address=shipping,
            )
        elif supplier_product.get("supplier") == "autods" and self.autods.is_configured():
            return self.autods.place_order(
                product_id=supplier_product["product_id"],
                shipping_address=shipping,
            )
        else:
            print(f"[OrderMonitor] No supplier match for '{product_name}' — manual required")
            return {"status": "manual_required", "product": product_name}

    def _extract_session_shipping(self, session) -> dict:
        """Extract shipping from a Stripe checkout session."""
        details = getattr(session, "shipping_details", None) or getattr(session, "shipping", None)
        if details and getattr(details, "address", None):
            addr = details.address
            return {
                "name": details.name or "",
                "address1": addr.line1 or "",
                "address2": addr.line2 or "",
                "city": addr.city or "",
                "state": addr.state or "",
                "zip": addr.postal_code or "",
                "country": addr.country or "",
                "email": getattr(session, "customer_email", "") or "",
                "phone": getattr(details, "phone", "") or "",
            }
        return None

    def _extract_shipping(self, charge) -> dict:
        if charge.shipping:
            addr = charge.shipping.address
            return {
                "name": charge.shipping.name,
                "address1": addr.line1,
                "address2": addr.line2 or "",
                "city": addr.city,
                "state": addr.state,
                "zip": addr.postal_code,
                "country": addr.country,
                "email": charge.billing_details.email or "",
                "phone": charge.shipping.phone or "",
            }
        return None

    def _load_product_map(self) -> dict:
        """Maps product name → supplier product ID."""
        map_path = BASE_DIR / "data" / "product_supplier_map.json"
        if not map_path.exists():
            return {}
        data = json.loads(map_path.read_text())
        # Strip metadata keys (prefixed with _) before returning
        return {k: v for k, v in data.items() if not k.startswith("_")}

    def _load_link_map(self) -> dict:
        """Maps Stripe payment link ID → product name (from stripe_links.json)."""
        links_path = BASE_DIR / "data" / "stripe_links.json"
        if not links_path.exists():
            return {}
        links = json.loads(links_path.read_text())
        return {link["id"]: link["product"] for link in links if "id" in link and "product" in link}

    def _log_order(self, order: dict):
        log_path = BASE_DIR / "data" / "order_log.json"
        orders = json.loads(log_path.read_text()) if log_path.exists() else []
        orders.append(order)
        log_path.write_text(json.dumps(orders, indent=2))


if __name__ == "__main__":
    from aliexpress_connector import AliExpressConnector
    print("Supplier Connector Status:")
    z = ZendropConnector()
    a = AutoDSConnector()
    ax = AliExpressConnector()
    print(f"  Zendrop:    {'✅ Ready' if z.is_configured() else '❌ Add ZENDROP_API_KEY'}")
    print(f"  AutoDS:     {'✅ Ready' if a.is_configured() else '❌ Add AUTODS_API_KEY'}")
    print(f"  AliExpress: {'✅ Ready' if ax.is_configured() else '❌ Add ALIEXPRESS_APP_KEY + ALIEXPRESS_APP_SECRET'}")
