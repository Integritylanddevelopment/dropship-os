"""Content marketing potential score.

Heuristic: 0..1 derived from signal-level cues - visual-demonstrability, problem-solving
language, curiosity hooks, before/after potential. We score from title+text keywords
without LLM calls (cheap, deterministic)."""
import re

VISUAL_DEMO = [
    "satisfying", "watch", "demo", "see how", "look at", "before and after", "transformation",
    "asmr", "oddly satisfying", "this is genius", "hack", "trick", "diy",
]
PROBLEM_SOLVING = [
    "stop", "prevent", "fix", "solve", "no more", "tired of", "struggle", "annoying",
    "frustrated", "fixes", "saves", "helps with", "for people who",
]
CURIOSITY = [
    "you won't believe", "amazing", "wait until", "watch what", "what happens",
    "trust me", "i can't believe", "obsessed", "everyone needs", "tiktok made me",
]
GIFTABLE = [
    "gift", "present", "for him", "for her", "for mom", "for dad", "stocking stuffer",
    "white elephant", "secret santa", "valentine", "birthday",
]

def score_signal_text(text: str) -> dict:
    if not text:
        return {"visual": 0, "problem": 0, "curiosity": 0, "giftable": 0, "total": 0.0}
    t = text.lower()
    v = sum(1 for k in VISUAL_DEMO if k in t)
    p = sum(1 for k in PROBLEM_SOLVING if k in t)
    c = sum(1 for k in CURIOSITY if k in t)
    g = sum(1 for k in GIFTABLE if k in t)
    raw = 0.4*min(v,3)/3 + 0.3*min(p,3)/3 + 0.2*min(c,3)/3 + 0.1*min(g,2)/2
    return {"visual": v, "problem": p, "curiosity": c, "giftable": g, "total": round(raw, 3)}

def aggregate_for_product(signals: list[dict]) -> dict:
    if not signals:
        return {"score": 0.0, "hooks": []}
    scores = []
    hooks = set()
    for s in signals:
        r = score_signal_text((s.get("title") or "") + " " + (s.get("text") or ""))
        scores.append(r["total"])
        if r["visual"]: hooks.add("visual-demo")
        if r["problem"]: hooks.add("problem-solving")
        if r["curiosity"]: hooks.add("curiosity-hook")
        if r["giftable"]: hooks.add("giftable")
    avg = sum(scores) / len(scores)
    return {"score": round(avg, 3), "hooks": sorted(hooks)}