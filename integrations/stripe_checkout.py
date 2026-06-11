#!/usr/bin/env python3
"""
integrations/stripe_checkout.py — Stripe Payment Link Generator
Creates Stripe products + payment links programmatically.
Links are embedded in landing pages via the Asset Machine.

Requires: STRIPE_SECRET_KEY in .env
Get it at: https://dashboard.stripe.com/apikeys
"""

import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")

try:
    import stripe
    STRIPE_AVAILABLE = bool(STRIPE_SECRET_KEY)
    if STRIPE_AVAILABLE:
        stripe.api_key = STRIPE_SECRET_KEY
except ImportError:
    STRIPE_AVAILABLE = False


class StripeCheckout:
    """Create Stripe products and payment links for dropship products."""

    def __init__(self):
        if not STRIPE_AVAILABLE:
            print("[Stripe] Not configured. Add STRIPE_SECRET_KEY to .env")

    def create_product_and_link(self, product_name: str, price_usd: float,
                                 description: str = None, image_url: str = None) -> dict:
        """
        Creates a Stripe product + payment link.
        Returns: {product_id, price_id, payment_link_url}
        """
        if not STRIPE_AVAILABLE:
            return {"error": "Stripe not configured", "payment_link_url": "#"}

        try:
            # Create product
            product_data = {"name": product_name}
            if description:
                product_data["description"] = description
            if image_url:
                product_data["images"] = [image_url]

            product = stripe.Product.create(**product_data)

            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(price_usd * 100),  # cents
                currency="usd",
            )

            # Create payment link
            payment_link = stripe.PaymentLink.create(
                line_items=[{"price": price.id, "quantity": 1}],
                after_completion={"type": "redirect", "redirect": {"url": os.getenv("STRIPE_SUCCESS_URL", "https://dropship-os-hazel.vercel.app/thank-you")}},  # noqa: E501
            )

            result = {
                "product_id": product.id,
                "price_id": price.id,
                "payment_link_id": payment_link.id,
                "payment_link_url": payment_link.url,
                "product_name": product_name,
                "price_usd": price_usd,
                "created_at": datetime.utcnow().isoformat(),
            }

            # Save to local registry
            self._save_link(result)
            print(f"[Stripe] ✅ Created: {product_name} | ${price_usd:.2f} | {payment_link.url}")
            return result

        except Exception as e:
            print(f"[Stripe] Error: {e}")
            return {"error": str(e), "payment_link_url": "#"}

    def list_payment_links(self) -> list:
        """Returns all active payment links."""
        registry_path = Path(__file__).parent.parent / "data" / "stripe_links.json"
        if registry_path.exists():
            return json.loads(registry_path.read_text())
        return []

    def get_payments(self, limit: int = 20) -> list:
        """Fetch recent successful payments from Stripe."""
        if not STRIPE_AVAILABLE:
            return []
        try:
            charges = stripe.Charge.list(limit=limit)
            return [
                {
                    "id": c.id,
                    "amount_usd": c.amount / 100,
                    "status": c.status,
                    "description": c.description,
                    "created": datetime.fromtimestamp(c.created).isoformat(),
                    "customer_email": c.billing_details.email if c.billing_details else None,
                }
                for c in charges.data
                if c.status == "succeeded"
            ]
        except Exception as e:
            print(f"[Stripe] Error fetching payments: {e}")
            return []

    def get_revenue_summary(self) -> dict:
        """Total revenue, order count, average order value."""
        payments = self.get_payments(limit=100)
        if not payments:
            return {"total_revenue": 0, "order_count": 0, "avg_order": 0}
        total = sum(p["amount_usd"] for p in payments)
        return {
            "total_revenue": round(total, 2),
            "order_count": len(payments),
            "avg_order": round(total / len(payments), 2),
            "last_payment": payments[0]["created"] if payments else None,
        }

    def _save_link(self, link_data: dict):
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        registry_path = data_dir / "stripe_links.json"
        links = json.loads(registry_path.read_text()) if registry_path.exists() else []
        links.append(link_data)
        registry_path.write_text(json.dumps(links, indent=2))


if __name__ == "__main__":
    sc = StripeCheckout()
    # Test: create a payment link for the top product
    result = sc.create_product_and_link(
        product_name="Automatic Pet Feeder",
        price_usd=34.99,
        description="The pet feeder that 10,000+ pet owners love. Ships in 7 days."
    )
    print(json.dumps(result, indent=2))
