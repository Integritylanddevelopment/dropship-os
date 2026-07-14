"""Build the final Product Opportunity Report for one clustered product.

Weights match the spec exactly:
- Downstream demand velocity: 30%
- Buyer intent: 20%
- Supplier availability/cost: 20%
- Content marketing potential: 15%
- Low saturation: 10%
- Shipping simplicity: 5%

Plus HARD AVOID FILTERS (per spec close):
- Legally risky (CBD, weapons, counterfeit, age-gated, FDA-regulated)
- Hard to ship (fragile, oversized, hazmat, perishable, lithium battery)
- Too saturated (on Amazon Movers AND many cheap supplier clones)
- Low margin (below 60% gross OR <3x landed cost)
- Hard to explain in short-form (technical language, no visual hook, long titles)

Any HARD filter failure forces recommendation = 'reject' with `rejection_reasons`.
Soft warnings get logged in `soft_warnings` without killing the candidate.
"""
from . import buyer_intent, trend_velocity, content_score, margin_calc, risk_filters

# Category-based supplier cost estimates (USD) for when no live supplier data
FALLBACK_COSTS = {
    "light": 4, "lights": 4, "led": 4, "lamp": 6, "strip": 3,
    "kitchen": 5, "gadget": 5, "tool": 6, "utensil": 3,
    "pet": 5, "dog": 5, "cat": 5, "collar": 3, "leash": 3, "toy": 2,
    "fitness": 7, "gym": 8, "yoga": 5, "band": 3, "resistance": 4,
    "posture": 6, "corrector": 6, "brace": 5, "support": 5,
    "phone": 3, "case": 2, "charger": 4, "holder": 3, "mount": 4, "stand": 5,
    "beauty": 5, "skin": 4, "serum": 5, "cream": 4, "mask": 3,
    "hair": 4, "brush": 3, "organizer": 5, "storage": 5,
    "speaker": 8, "headphone": 7, "earbuds": 6, "wireless": 6,
    "watch": 8, "clock": 5, "plant": 4, "planter": 4, "garden": 5,
    "massage": 8, "gun": 10, "roller": 4, "cleaner": 6, "vacuum": 12,
    "bottle": 3, "flask": 4, "cup": 3, "mug": 3, "bag": 5, "backpack": 8,
    "wallet": 4, "pillow": 5, "blanket": 6, "rug": 8, "mat": 4,
    "camera": 10, "tripod": 6, "pen": 2, "notebook": 3,
    "fan": 5, "heater": 8, "humidifier": 7,
}
FALLBACK_DEFAULT_COST = 6.0  # generic dropship item estimate

def _estimate_supplier_cost(keyword: str) -> float:
    """Estimate supplier cost from product keyword when no live supplier data."""
    if not keyword:
        return FALLBACK_DEFAULT_COST
    kw = keyword.lower()
    for term, cost in FALLBACK_COSTS.items():
        if term in kw:
            return float(cost)
    return FALLBACK_DEFAULT_COST

WEIGHTS = {
    "demand_velocity": 0.30,
    "buyer_intent": 0.20,
    "supplier": 0.20,
    "content": 0.15,
    "saturation": 0.10,
    "shipping": 0.05,
}

def _supplier_score(suppliers):
    if not suppliers:
        return 0.3  # partial credit — product exists but no confirmed supplier yet
    best = min((s.get("unit_cost", 999) for s in suppliers if s.get("unit_cost", 0) > 0), default=999)
    score = 0.5
    if best < 10: score += 0.3
    if best < 5: score += 0.2
    return min(1.0, score)

def _saturation_score(signals, suppliers):
    platforms = {s.get("platform") for s in signals}
    if "amazon_movers" in platforms and len(platforms) <= 2:
        return 0.3
    if "youtube" in platforms and "reddit" in platforms and "amazon_movers" not in platforms:
        return 0.85
    return 0.6

def _shipping_score(suppliers, soft_shipping_warnings):
    if not suppliers: return 0.5
    # If we found shipping risk soft-warnings, penalize even when not hard-rejected
    if soft_shipping_warnings: return 0.3
    return 0.7

def build(product_keyword, signals, suppliers, force_retail=None):
    bi = buyer_intent.aggregate_for_product(signals)
    vel = trend_velocity.velocity_score(signals)
    ct = content_score.aggregate_for_product(signals)
    sup = _supplier_score(suppliers)
    sat = _saturation_score(signals, suppliers)

    # Margin first because risk-filter wants to know
    if suppliers:
        cheapest = min(suppliers, key=lambda s: s.get("unit_cost") or 999)
        margin = margin_calc.compute(
            supplier_cost=cheapest.get("unit_cost") or 0,
            shipping_cost=4.00,
            retail_price=force_retail,
        )
    else:
        # Fallback: estimate supplier cost from product category so scoring
        # still produces meaningful results even without live supplier data.
        est_cost = _estimate_supplier_cost(product_keyword)
        margin = margin_calc.compute(
            supplier_cost=est_cost,
            shipping_cost=4.00,
            retail_price=force_retail,
        )
        # Flag as estimated so downstream knows
        margin["estimated"] = True

    # HARD AVOID FILTERS
    rejected, rejection_reasons, soft_warnings = risk_filters.evaluate(signals, suppliers, margin)

    ship = _shipping_score(suppliers, [w for w in soft_warnings if "shipping" in w])

    overall = (
        WEIGHTS["demand_velocity"] * vel +
        WEIGHTS["buyer_intent"] * bi +
        WEIGHTS["supplier"] * sup +
        WEIGHTS["content"] * ct["score"] +
        WEIGHTS["saturation"] * sat +
        WEIGHTS["shipping"] * ship
    )
    margin_factor = 1.0 if margin.get("passes_margin_floor") else 0.7
    overall *= margin_factor

    if rejected:
        rec = "reject"
        # Zero out overall display so rejected items don't accidentally rank high
        overall = round(overall * 0.4, 3)
    else:
        rec = _recommend(overall, margin)

    top_signals = sorted(signals, key=lambda s: s.get("score") or 0, reverse=True)[:3]
    top_suppliers = sorted(suppliers, key=lambda s: s.get("unit_cost") or 999)[:3]

    return {
        "product_keyword": product_keyword,
        "category": _infer_category(signals),
        "scores": {
            "demand_velocity": round(vel, 3),
            "buyer_intent": round(bi, 3),
            "supplier_availability": round(sup, 3),
            "content_potential": round(ct["score"], 3),
            "low_saturation": round(sat, 3),
            "shipping_simplicity": round(ship, 3),
            "margin": round(margin.get("margin_score", 0), 3),
            "overall": round(overall, 3),
        },
        "margin": margin,
        "content_hooks": ct.get("hooks", []),
        "buyer_intent_phrases": sorted({p for s in signals for p in (s.get("buyer_intent_hits") or [])}),
        "n_signals": len(signals),
        "n_suppliers": len(suppliers),
        "top_social_sources": [{"platform": s.get("platform"), "url": s.get("source_url"), "title": s.get("title")} for s in top_signals],
        "top_suppliers": [{"supplier": s.get("supplier"), "url": s.get("supplier_url"), "unit_cost": s.get("unit_cost"), "title": s.get("title")} for s in top_suppliers],
        "rejection_reasons": rejection_reasons,
        "soft_warnings": soft_warnings,
        "recommendation": rec,
    }

def _infer_category(signals):
    cats = [s.get("category") for s in signals if s.get("category")]
    if cats:
        return max(set(cats), key=cats.count)
    return ""

def _recommend(overall, margin):
    if not margin.get("passes_margin_floor"):
        if overall > 0.7: return "watch"
        return "skip"
    if overall >= 0.7: return "pursue"
    if overall >= 0.5: return "test"
    if overall >= 0.35: return "watch"
    return "skip"