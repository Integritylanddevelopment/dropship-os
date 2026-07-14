"""Buyer-intent score: how strongly the signal text shows purchase intent."""
from collections import Counter

WEIGHT = {
    "where can i buy": 5, "where to buy": 5, "link please": 4, "drop the link": 4,
    "need this": 3, "amazon link": 4, "tiktok made me buy": 5, "tiktok shop link": 5,
    "does this ship": 4, "is this available": 3, "where did you get": 3,
    "ordering this": 4, "buying this": 4, "added to cart": 4,
    "shut up and take my money": 5, "comment for link": 3,
    "link in bio": 2, "what brand": 2, "how much": 2, "i need this in my life": 4,
}

def score_signal(signal: dict) -> float:
    hits = signal.get("buyer_intent_hits") or []
    if not hits:
        return 0.0
    raw = sum(WEIGHT.get(h, 1) for h in hits)
    # cap at 1.0
    return min(1.0, raw / 10.0)

def aggregate_for_product(signals: list[dict]) -> float:
    """Buyer-intent score for a product cluster.

    Uses a weighted approach: the BEST intent signals matter most, and having
    ANY intent-bearing signals in the cluster is itself a positive signal.
    Pure averaging dilutes score to near-zero when most signals lack intent.
    """
    if not signals:
        return 0.0
    scores = [score_signal(s) for s in signals]
    nonzero = [s for s in scores if s > 0]
    if not nonzero:
        return 0.0
    # Penetration: what fraction of signals show intent (capped at 0.5)
    penetration = min(0.5, len(nonzero) / len(scores))
    # Strength: average of intent-bearing signals
    strength = sum(nonzero) / len(nonzero)
    # Combined: strong intent in even a few signals is meaningful
    return min(1.0, 0.6 * strength + 0.4 * (penetration * 2))