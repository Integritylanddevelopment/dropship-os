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
    """Average normalized buyer-intent across signals for one product cluster."""
    if not signals:
        return 0.0
    scores = [score_signal(s) for s in signals]
    return sum(scores) / len(scores)