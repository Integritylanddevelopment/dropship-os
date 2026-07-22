import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""Order fulfillment: Stripe payments -> CJ Dropshipping orders, automatically.

The last mile. A background loop polls Stripe for paid checkouts. Each new
order is matched to its product in the library, then auto-fulfilled at CJ
(order placed with the BUYER's shipping address; CJ ships direct).

Money-safety fuse — an order goes to NEEDS REVIEW instead of auto-ordering when:
  - the CJ product has multiple variants (size/color ambiguity)
  - the CJ cost exceeds FULFILL_MAX_COST (default $30)
  - no phone number available (CJ requires one)
  - product can't be confidently matched at CJ
Review orders are fulfilled with one click from the Orders panel.
"""
import os
import json
import time
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    _root = Path(__file__).parent.parent
    load_dotenv(_root / ".env")
    load_dotenv(_root / ".env.local", override=True)
except ImportError:
    pass

SHIPSTACK_ROOT = Path(__file__).parent.parent
ORDERS_PATH = SHIPSTACK_ROOT / "data" / "orders.json"
LIBRARY_PATH = SHIPSTACK_ROOT / "data" / "product_library.json"

STRIPE_API = "https://api.stripe.com/v1"
FULFILL_MAX_COST = float(os.getenv("FULFILL_MAX_COST", "30"))
FULFILL_PHONE = os.getenv("SHIPSTACK_FULFILL_PHONE", "")
AUTO_FULFILL = os.getenv("AUTO_FULFILL", "1") not in ("0", "false", "False")

_LOCK = threading.Lock()


# ── HTTP helpers ─────────────────────────────────────────────────────────

def _stripe_get(path: str, params: dict | None = None) -> dict:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        return {"error": "STRIPE_SECRET_KEY not set"}
    url = f"{STRIPE_API}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}


# ── Order store ──────────────────────────────────────────────────────────

def _load_orders() -> dict:
    try:
        return json.loads(ORDERS_PATH.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _save_orders(orders: dict):
    ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ORDERS_PATH.write_text(json.dumps(orders, indent=2, ensure_ascii=False), encoding="utf-8")


def list_orders() -> list:
    orders = list(_load_orders().values())
    orders.sort(key=lambda o: o.get("created", ""), reverse=True)
    return orders


# ── Stripe polling ───────────────────────────────────────────────────────

def _library_by_title() -> dict:
    try:
        lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8", errors="replace"))
        return {v.get("title", "").strip().lower(): v for v in lib.values()}
    except Exception:
        return {}


def poll_stripe() -> dict:
    """Pull recent checkout sessions, add newly PAID ones to the order store.
    Returns {new: n, total: n} or {error}."""
    sessions = _stripe_get("checkout/sessions", {"limit": 40})
    if "error" in sessions:
        return {"error": str(sessions["error"])[:200]}
    lib_map = _library_by_title()
    orders = _load_orders()
    new_count = 0

    for s in sessions.get("data", []):
        sid = s.get("id", "")
        if not sid or sid in orders:
            continue
        if s.get("payment_status") != "paid":
            continue

        # What did they buy?
        items = _stripe_get(f"checkout/sessions/{sid}/line_items", {"limit": 5})
        product_title = ""
        if items.get("data"):
            product_title = (items["data"][0].get("description") or "").strip()

        cust = s.get("customer_details") or {}
        ship = s.get("shipping_details") or s.get("collected_information", {}).get("shipping_details") or {}
        addr = (ship.get("address") or cust.get("address") or {})

        lib_entry = lib_map.get(product_title.lower(), {})

        orders[sid] = {
            "session_id": sid,
            "created": datetime.fromtimestamp(s.get("created", time.time()), tz=timezone.utc).isoformat(),
            "amount": round((s.get("amount_total") or 0) / 100, 2),
            "currency": (s.get("currency") or "usd").upper(),
            "product_title": product_title or "(unknown product)",
            "product_id": lib_entry.get("product_id", ""),
            "buyer_name": ship.get("name") or cust.get("name") or "",
            "buyer_email": cust.get("email") or "",
            "buyer_phone": cust.get("phone") or "",
            "address": {
                "line1": addr.get("line1", ""), "line2": addr.get("line2", "") or "",
                "city": addr.get("city", ""), "state": addr.get("state", ""),
                "zip": addr.get("postal_code", ""), "country": addr.get("country", "US"),
            },
            "status": "new",
            "fulfillment": {},
        }
        new_count += 1

    if new_count:
        _save_orders(orders)
    return {"new": new_count, "total": len(orders)}


# ── CJ fulfillment ───────────────────────────────────────────────────────

def _cj_token():
    from discovery_engine.suppliers import cj_dropshipping
    return cj_dropshipping._get_token()


def _cj_api(path: str, method: str = "GET", body: dict | None = None, params: dict | None = None) -> dict:
    from discovery_engine.suppliers import cj_dropshipping
    tok = _cj_token()
    if not tok:
        return {"error": "CJ not configured"}
    url = f"{cj_dropshipping.BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return cj_dropshipping._http_json(url, method=method, body=body,
                                      headers={"CJ-Access-Token": tok}, timeout=30)


def _resolve_cj_product(order: dict) -> dict:
    """Find the CJ product + variant for this order.
    Returns {pid, vid, cost, variants_n} or {error}/{review: reason}."""
    from discovery_engine.suppliers import cj_dropshipping

    # Prefer the CJ product id saved in the library
    pid = ""
    try:
        lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8", errors="replace"))
        entry = lib.get(order.get("product_id") or "", {})
        pid = entry.get("cj_pid", "")
    except Exception:
        pass

    if not pid:
        # Search CJ by the product title
        title = order.get("product_title", "")
        results = cj_dropshipping.search(" ".join(title.split()[:4]), limit=5)
        if not results:
            return {"review": "Couldn't find this product at CJ automatically"}
        pid = results[0].get("id", "")
        if not pid:
            return {"review": "CJ listing has no product id"}

    detail = _cj_api("product/query", params={"pid": pid})
    data = detail.get("data") or {}
    variants = data.get("variants") or []
    if not variants:
        return {"review": "CJ listing has no orderable variants"}

    in_stock = [v for v in variants if (v.get("variantSellPrice") or 0) > 0]
    if not in_stock:
        in_stock = variants
    cheapest = min(in_stock, key=lambda v: float(v.get("variantSellPrice") or 999))
    cost = float(cheapest.get("variantSellPrice") or 0)

    result = {"pid": pid, "vid": cheapest.get("vid", ""), "cost": cost,
              "variants_n": len(variants)}
    if len(variants) > 1:
        prices = [float(v.get("variantSellPrice") or 0) for v in in_stock]
        spread = (max(prices) - min(prices)) / max(min(prices), 0.01)
        if spread > 0.2:
            result["review"] = (f"{len(variants)} variants with different prices — "
                                f"pick the right size/color before ordering")
    if cost > FULFILL_MAX_COST:
        result["review"] = f"CJ cost ${cost:.2f} is above the ${FULFILL_MAX_COST:.0f} auto-limit"
    return result


def fulfill_order(session_id: str, force: bool = False) -> dict:
    """Place the CJ order for one paid Stripe order. force=True skips the review fuse."""
    orders = _load_orders()
    order = orders.get(session_id)
    if not order:
        return {"ok": False, "error": "Order not found"}
    if order.get("status") in ("ordered", "shipped", "done"):
        return {"ok": False, "error": "Already fulfilled"}

    addr = order.get("address") or {}
    if not (addr.get("line1") and addr.get("city") and addr.get("zip")):
        order["status"] = "needs_review"
        order["fulfillment"] = {"reason": "Missing shipping address from Stripe"}
        orders[session_id] = order; _save_orders(orders)
        return {"ok": False, "error": "Missing shipping address"}

    phone = order.get("buyer_phone") or FULFILL_PHONE
    if not phone:
        order["status"] = "needs_review"
        order["fulfillment"] = {"reason": "No phone number — add SHIPSTACK_FULFILL_PHONE to .env (CJ requires one)"}
        orders[session_id] = order; _save_orders(orders)
        return {"ok": False, "error": "No phone number for shipping"}

    resolved = _resolve_cj_product(order)
    if resolved.get("error"):
        order["status"] = "failed"
        order["fulfillment"] = {"reason": resolved["error"]}
        orders[session_id] = order; _save_orders(orders)
        return {"ok": False, "error": resolved["error"]}
    if resolved.get("review") and not force:
        order["status"] = "needs_review"
        order["fulfillment"] = {"reason": resolved["review"], "pid": resolved.get("pid", ""),
                                "vid": resolved.get("vid", ""), "cost": resolved.get("cost", 0)}
        orders[session_id] = order; _save_orders(orders)
        return {"ok": False, "review": resolved["review"]}

    payload = {
        "orderNumber": f"SS-{session_id[-10:]}",
        "shippingCustomerName": order.get("buyer_name") or "Customer",
        "shippingCountryCode": addr.get("country", "US"),
        "shippingCountry": addr.get("country", "US"),
        "shippingProvince": addr.get("state", ""),
        "shippingCity": addr.get("city", ""),
        "shippingAddress": (addr.get("line1", "") + (" " + addr.get("line2", "") if addr.get("line2") else "")).strip(),
        "shippingZip": addr.get("zip", ""),
        "shippingPhone": phone,
        "remark": "ShipStack auto-fulfillment",
        "logisticName": "CJPacket Ordinary",
        "fromCountryCode": "CN",
        "products": [{"vid": resolved["vid"], "quantity": 1}],
    }
    resp = _cj_api("shopping/order/createOrder", method="POST", body=payload)

    if resp.get("result") in (True, "true") or (resp.get("data") and not resp.get("error")):
        cj_order_id = ""
        d = resp.get("data")
        if isinstance(d, dict):
            cj_order_id = d.get("orderId") or d.get("orderNumber") or ""
        elif isinstance(d, str):
            cj_order_id = d
        order["status"] = "ordered"
        order["fulfillment"] = {"cj_order_id": cj_order_id, "cj_cost": resolved.get("cost", 0),
                                "placed_at": datetime.now(timezone.utc).isoformat()}
        orders[session_id] = order; _save_orders(orders)
        return {"ok": True, "cj_order_id": cj_order_id}
    else:
        msg = str(resp.get("message") or resp.get("error") or resp)[:250]
        order["status"] = "needs_review"
        order["fulfillment"] = {"reason": f"CJ rejected the order: {msg}"}
        orders[session_id] = order; _save_orders(orders)
        return {"ok": False, "error": msg}


def refresh_tracking() -> int:
    """Check CJ for tracking numbers on ordered items. Returns how many updated."""
    orders = _load_orders()
    updated = 0
    for sid, o in orders.items():
        if o.get("status") != "ordered":
            continue
        cj_id = (o.get("fulfillment") or {}).get("cj_order_id", "")
        if not cj_id:
            continue
        resp = _cj_api("shopping/order/getOrderDetail", params={"orderId": cj_id})
        d = resp.get("data") or {}
        tracking = d.get("trackNumber") or d.get("trackingNumber") or ""
        if tracking:
            o["status"] = "shipped"
            o["fulfillment"]["tracking"] = tracking
            updated += 1
    if updated:
        _save_orders(orders)
    return updated


def mark_done(session_id: str) -> dict:
    orders = _load_orders()
    if session_id in orders:
        orders[session_id]["status"] = "done"
        _save_orders(orders)
        return {"ok": True}
    return {"ok": False, "error": "not found"}


# ── The automation loop ──────────────────────────────────────────────────

def process_cycle() -> dict:
    """One full cycle: poll Stripe -> auto-fulfill new orders -> refresh tracking."""
    out = {"polled": None, "fulfilled": [], "tracking_updates": 0}
    p = poll_stripe()
    out["polled"] = p
    if AUTO_FULFILL and not p.get("error"):
        for o in list_orders():
            if o.get("status") == "new":
                r = fulfill_order(o["session_id"])
                out["fulfilled"].append({"order": o["product_title"], "result": r})
    try:
        out["tracking_updates"] = refresh_tracking()
    except Exception:
        pass
    return out


def start_background_loop(interval_sec: int = 300):
    """Engine calls this once at boot. Checks for new orders every 5 minutes."""
    def loop():
        while True:
            try:
                process_cycle()
            except Exception:
                pass
            time.sleep(interval_sec)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
