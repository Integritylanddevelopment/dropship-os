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

WEIGHTS = {
    "demand_velocity": 0.30,
    "buyer_intent": 0.20,
    "supplier": 0.20,
    "content": 0.15,
    "saturation": 0.10,
    "shipping": 0.05,
}

def _supplier_score(suppliers):
    if not suppliers: return 0.0
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
        margin = {"margin_score": 0, "landed_cost": 0, "retail_price": 0,
                  "gross_margin": 0, "gross_margin_pct": 0, "passes_margin_floor": False}

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