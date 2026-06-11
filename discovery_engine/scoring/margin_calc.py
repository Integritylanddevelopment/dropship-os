"""Margin and pricing math.

Conservative defaults for fees/CPA so estimates skew low (under-promise).
Adjust DEFAULTS via env or per-call args."""

DEFAULTS = {
    "platform_fee_pct": 0.029,        # Shopify/Stripe-ish
    "payment_fee_flat": 0.30,         # per-order
    "ad_cpa_default": 12.00,          # USD, conservative TikTok/Meta CPA for low-ticket
    "content_production_per_test": 50.00,
    "fulfillment_handling": 1.50,     # supplier-side pick/pack overhead
    "min_target_margin": 0.60,
    "min_price_multiplier": 3.0,
}

def estimate_retail_price(supplier_cost: float, shipping_cost: float, multiplier: float | None = None) -> float:
    mult = multiplier or DEFAULTS["min_price_multiplier"]
    landed = supplier_cost + shipping_cost + DEFAULTS["fulfillment_handling"]
    return round(landed * mult, 2)

def compute(supplier_cost: float, shipping_cost: float = 4.00,
            retail_price: float | None = None,
            ad_cpa: float | None = None) -> dict:
    landed = supplier_cost + shipping_cost + DEFAULTS["fulfillment_handling"]
    retail = retail_price if retail_price else estimate_retail_price(supplier_cost, shipping_cost)
    cpa = ad_cpa if ad_cpa is not None else DEFAULTS["ad_cpa_default"]
    platform_fee = retail * DEFAULTS["platform_fee_pct"] + DEFAULTS["payment_fee_flat"]
    gross_margin = retail - landed
    gross_margin_pct = (gross_margin / retail) if retail else 0
    net_margin = gross_margin - platform_fee - cpa
    net_margin_pct = (net_margin / retail) if retail else 0
    break_even_cpa = max(0.0, gross_margin - platform_fee)
    passes_gross = gross_margin_pct >= DEFAULTS["min_target_margin"]
    passes_mult = retail >= (landed * DEFAULTS["min_price_multiplier"])
    return {
        "landed_cost": round(landed, 2),
        "retail_price": round(retail, 2),
        "platform_fee": round(platform_fee, 2),
        "ad_cpa_assumed": round(cpa, 2),
        "gross_margin": round(gross_margin, 2),
        "gross_margin_pct": round(gross_margin_pct, 3),
        "net_margin": round(net_margin, 2),
        "net_margin_pct": round(net_margin_pct, 3),
        "break_even_cpa": round(break_even_cpa, 2),
        "passes_margin_floor": passes_gross and passes_mult,
        "margin_score": _to_01(gross_margin_pct),
    }

def _to_01(pct: float) -> float:
    # 0.30 margin -> 0.0, 0.60 -> 0.5, 0.85+ -> 1.0
    if pct <= 0.30: return 0.0
    if pct >= 0.85: return 1.0
    return (pct - 0.30) / 0.55