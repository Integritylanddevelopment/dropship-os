"""Hard-rejection risk filters per spec:

  > Avoid products that are already too saturated, hard to ship, legally risky,
  > low margin, or impossible to explain quickly in short-form content.

Each filter returns (failed: bool, reasons: list[str]). The opportunity report
runs every filter and forces recommendation = 'reject' if ANY hard filter fires.
Soft signals (high-but-not-blocker risk) still produce a 'watch' instead of
killing the candidate outright.
"""
import re

# ---------------------------------------------------------------------------
# Legal / policy risk
# ---------------------------------------------------------------------------
LEGAL_RED_FLAGS = [
    # Controlled substances / drug-adjacent
    "cbd", "thc", "kratom", "delta-8", "delta 8", "delta-9", "delta 9", "nicotine",
    "vape", "e-cigarette", "ecig", "hemp flower", "marijuana", "psilocybin", "kava",
    # Weapons / weapons-adjacent
    "knife", "ammo", "ammunition", "firearm", "gun ", "magazine ", "silencer",
    "suppressor", "taser", "stun gun", "brass knuckle", "throwing star", "ninja star",
    "pepper spray", "tactical pen", "self-defense baton", "switchblade",
    # Medical claims (FDA / FTC)
    "cures", "treats cancer", "alternative to insulin", "fda approved" + " " + "dietary",
    "clinically proven", "doctor recommended", "miracle cure",
    # Counterfeit / IP risk
    "louis vuitton", "gucci", "rolex", "supreme", "nike air", "adidas yeezy",
    "apple airpod", "airpods replica", "replica ", "1:1 replica", "knockoff",
    "inspired by", "dupe of",
    # Age-gated
    "alcohol", "adult toy", "fleshlight", "vibrator", "sex toy",
    # Customs / quarantine risk
    "live plant", "seeds", "exotic animal", "ivory", "tortoiseshell", "coral",
    # Restricted / regulated
    "prescription", "rx ", "antibiotics", "steroid", "ozempic", "semaglutide",
]

# Suppliers that often list grey-market products
SUPPLIER_TITLE_FLAGS = ["replica", "1:1", "copy of", "fake "]

def legal_risk(signals, suppliers):
    reasons = []
    for s in signals + suppliers:
        text = ((s.get("title") or "") + " " + (s.get("text") or "")).lower()
        for flag in LEGAL_RED_FLAGS:
            if flag in text:
                reasons.append(f"legal_flag:{flag}")
                break
    for sup in suppliers:
        t = (sup.get("title") or "").lower()
        for flag in SUPPLIER_TITLE_FLAGS:
            if flag in t:
                reasons.append(f"supplier_grey_market:{flag}")
                break
    failed = bool(reasons)
    return failed, list(dict.fromkeys(reasons))  # dedupe

# ---------------------------------------------------------------------------
# Shipping risk
# ---------------------------------------------------------------------------
SHIPPING_HARD_FLAGS = [
    # Fragile
    "glass ", "ceramic ", "porcelain", "crystal ", "mirror ",
    # Oversized
    "couch", "sofa", "mattress", "bed frame", "treadmill", "rowing machine",
    "kayak", "surfboard", "skateboard deck", "trampoline", "swing set",
    # Hazmat / restricted carriers
    "lithium battery", "li-ion battery", "lipo battery", "aerosol", "flammable",
    "propane", "compressed gas", "powerful magnet",  # bare "magnetic" matches normal magnetic phone holders, drop it
    # Perishable
    "perishable", "fresh food", "frozen ", "live fish", "live insect", "live plant",
    # Liquid in bulk
    "gallon of", "5-gallon", "5 gallon", "55 gallon",
]

def shipping_risk(signals, suppliers):
    """Only inspect SUPPLIER titles/text, not signal context.

    Why: a Reddit comment like "saves my couch from pet hair" mentions 'couch'
    but the product is a small pet hair roller. Anchor shipping risk to what the
    supplier is actually selling."""
    reasons = []
    blob = " ".join((s.get("title") or "") + " " + (s.get("text") or "")
                    for s in suppliers).lower()
    for flag in SHIPPING_HARD_FLAGS:
        if flag in blob:
            reasons.append(f"shipping_flag:{flag.strip()}")
    failed = len(reasons) >= 1
    return failed, list(dict.fromkeys(reasons))

# ---------------------------------------------------------------------------
# Saturation risk
# ---------------------------------------------------------------------------
def saturation_risk(signals, suppliers):
    """Hard reject if BOTH:
      - product already on Amazon Movers (proxy for trending-on-Amazon),
      - AND there are 5+ supplier matches with similar low cost
        (means dozens of stores already source from same suppliers).
    Otherwise return soft signal in `reasons` and do not fail.
    """
    reasons = []
    platforms = {s.get("platform") for s in signals}
    has_amazon = "amazon_movers" in platforms
    n_cheap_suppliers = sum(1 for s in suppliers if (s.get("unit_cost") or 999) < 8)
    if has_amazon and n_cheap_suppliers >= 5:
        reasons.append("saturated:on_amazon_movers_with_many_cheap_suppliers")
        return True, reasons
    if has_amazon:
        reasons.append("soft:already_on_amazon_movers")
    if n_cheap_suppliers >= 8:
        reasons.append("soft:many_supplier_clones")
    return False, reasons

# ---------------------------------------------------------------------------
# Explainability risk - can this be shown in <15s of short-form?
# ---------------------------------------------------------------------------
HARD_TO_EXPLAIN_SIGNALS = [
    "technical", "specification", "datasheet", "calibration",
    "configuration", "firmware", "schematic", "calibrated",
    "industrial", "wholesale lot", "raw material", "oem ",
]
EASY_EXPLAIN_HOOKS = [
    "satisfying", "before and after", "hack", "trick", "demo", "watch", "look",
    "asmr", "solves", "fixes", "no more", "transformation", "tiktok made me",
    "saves you", "stops", "prevents",
]

def explainability_risk(signals):
    """Fail if no easy-explain hook AND has hard-to-explain language AND average
    title length > 12 words (suggests technical/specs-heavy product)."""
    reasons = []
    if not signals:
        return True, ["no_signals_to_assess_explainability"]
    text_blob = " ".join((s.get("title") or "") + " " + (s.get("text") or "")
                         for s in signals).lower()
    has_easy = any(h in text_blob for h in EASY_EXPLAIN_HOOKS)
    has_hard = any(h in text_blob for h in HARD_TO_EXPLAIN_SIGNALS)
    titles = [s.get("title") or "" for s in signals if s.get("title")]
    avg_words = sum(len(t.split()) for t in titles) / max(len(titles), 1)
    if has_hard and not has_easy:
        reasons.append("complex_language_no_easy_hook")
    if avg_words > 14:
        reasons.append(f"avg_title_words_high:{avg_words:.1f}")
    if not has_easy and avg_words > 12:
        reasons.append("no_visual_hook_and_long_titles")
    failed = ("complex_language_no_easy_hook" in reasons) or \
             ("no_visual_hook_and_long_titles" in reasons)
    return failed, reasons

# ---------------------------------------------------------------------------
# Margin gate (hard floor pulled from spec: 60% gross OR 3x landed)
# ---------------------------------------------------------------------------
def margin_floor_risk(margin: dict):
    """Hard reject if margin floor missed AND there ARE suppliers (so we have data)."""
    if not margin:
        return False, []  # no data, defer to soft scoring
    if margin.get("passes_margin_floor"):
        return False, []
    if margin.get("landed_cost", 0) <= 0:
        return False, ["soft:no_supplier_data_for_margin_check"]
    reasons = [f"margin_below_floor:{margin.get('gross_margin_pct',0):.0%}"]
    return True, reasons

# ---------------------------------------------------------------------------
# Top-level evaluator
# ---------------------------------------------------------------------------
def evaluate(signals, suppliers, margin: dict):
    """Run all filters. Returns (rejected: bool, reasons: list[str], soft_warnings: list[str])."""
    rejected = False
    reasons = []
    soft = []
    for name, fn in [
        ("legal",          lambda: legal_risk(signals, suppliers)),
        ("shipping",       lambda: shipping_risk(signals, suppliers)),
        ("saturation",     lambda: saturation_risk(signals, suppliers)),
        ("explainability", lambda: explainability_risk(signals)),
        ("margin",         lambda: margin_floor_risk(margin)),
    ]:
        failed, rs = fn()
        if failed:
            rejected = True
            reasons.extend(f"{name}:{r}" for r in rs if not r.startswith("soft:"))
        for r in rs:
            if r.startswith("soft:"):
                soft.append(f"{name}:{r[5:]}")
    return rejected, reasons, soft