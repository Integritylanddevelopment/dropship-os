"""
avatar_engine.py — Demographic Avatar Engine for ShipStack
==========================================================
Defines customer personas and generates content variants
tuned to each avatar's language, pain points, and buying triggers.

Avatars are the engine behind A/B testing — every post gets
variants written FOR specific people, not just "general audience."
"""

import json
import os
from pathlib import Path
from typing import Optional
import requests

try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

OLLAMA_URL   = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
BASE_DIR     = Path(__file__).parent.parent
LEARNING_DIR = BASE_DIR / "data" / "learning"

# DB layer — avatar learned patterns stored in SQLite learning_state table
from agents.db import LearningDB as _LearningDB, init_db as _init_db
_init_db()
_ldb = _LearningDB()


# ── Avatar definitions ────────────────────────────────────────────────────────
# Each avatar = a real buyer type with distinct language, triggers, objections

AVATARS = {
    "gen_z_female": {
        "name": "Gen Z Girl",
        "age_range": "16–24",
        "gender": "Female",
        "income": "Low–Medium",
        "platform_primary": ["tiktok", "instagram"],
        "language_style": "casual, internet slang, lowercase, humor",
        "vocab": ["slay", "obsessed", "no bc", "bestie", "girl math", "periodt",
                  "hits different", "understood the assignment", "ate", "ate that",
                  "lowkey", "not me", "POV:", "the way", "girly pop"],
        "hook_triggers": ["trend", "viral", "everyone's buying", "POV:", "girl math"],
        "pain_points": ["budget", "wanting to look good", "FOMO", "fitting in", "self-expression"],
        "buying_triggers": ["everyone has it", "trend", "aesthetic", "cheap find", "dupe"],
        "objections": ["is it worth it", "will it actually work", "is it fast shipping"],
        "cta_style": "casual and fun — 'comment INFO bestie' or 'link in bio girly'",
        "content_energy": "high energy, playful, self-aware humor",
        "example_hook": "POV: you finally found the thing that actually works 😭",
        "example_cta": "comment 'SEND IT' and I'll dm you the link bestie 💌",
    },
    "millennial_female": {
        "name": "Millennial Woman",
        "age_range": "28–38",
        "gender": "Female",
        "income": "Medium–High",
        "platform_primary": ["instagram", "tiktok", "youtube"],
        "language_style": "conversational, relatable, slightly skeptical, proof-seeking",
        "vocab": ["honestly", "real talk", "game changer", "life-changing", "obsessed",
                  "I was skeptical but", "after X weeks", "honest review", "finally",
                  "I wish I'd found this sooner", "10/10", "would recommend"],
        "hook_triggers": ["honest review", "I tested", "skeptic turned believer", "results"],
        "pain_points": ["busy schedule", "wasted money on things that don't work", "wanting real results"],
        "buying_triggers": ["social proof", "before/after results", "time savings", "quality"],
        "objections": ["is it really worth the price", "how long does it take to work"],
        "cta_style": "direct and value-forward — 'link in bio, comes with free shipping'",
        "content_energy": "warm, trustworthy, personal story arc",
        "example_hook": "I was today years old when I found out about this and I'm lowkey upset it took so long",
        "example_cta": "Link in bio — I also found a discount code that still works 🙌",
    },
    "budget_shopper": {
        "name": "Budget Buyer",
        "age_range": "18–45",
        "gender": "Any",
        "income": "Low–Medium",
        "platform_primary": ["tiktok", "instagram"],
        "language_style": "value-focused, deal-hunting, price-first",
        "vocab": ["dupe", "found it cheaper", "Amazon find", "under $20", "budget friendly",
                  "steals and deals", "saves money", "worth every penny", "cheap alternative",
                  "price drop", "sale", "limited time"],
        "hook_triggers": ["cheap", "dupe", "Amazon find", "under $X", "deals"],
        "pain_points": ["money", "not wanting to overpay", "finding value"],
        "buying_triggers": ["price", "value vs cost", "free shipping", "discount code"],
        "objections": ["why is it so cheap", "is the quality good for the price"],
        "cta_style": "urgency on price — 'grab it before the price goes back up'",
        "content_energy": "excited find, deal-hunter energy",
        "example_hook": "I found the $12 version of that $80 thing everyone's buying",
        "example_cta": "Price dropping soon — link in bio before it goes back up 🔥",
    },
    "premium_buyer": {
        "name": "Premium Buyer",
        "age_range": "28–48",
        "gender": "Any",
        "income": "Medium–High",
        "platform_primary": ["instagram", "youtube"],
        "language_style": "quality-focused, aspirational, lifestyle-oriented",
        "vocab": ["investment piece", "worth it", "premium", "elevated", "luxe", "high-quality",
                  "well-made", "pays for itself", "lasts forever", "finally a product that"],
        "hook_triggers": ["quality", "investment", "lasts", "premium feel", "worth the price"],
        "pain_points": ["wasting money on cheap things that break", "wanting quality"],
        "buying_triggers": ["quality signals", "longevity", "status", "lifestyle fit"],
        "objections": ["is the quality actually good", "will it last"],
        "cta_style": "confident and benefit-focused — 'link in bio, free returns'",
        "content_energy": "calm, aspirational, confident",
        "example_hook": "Stop buying the cheap version. This is what actually lasts.",
        "example_cta": "Link in bio — ships in 2 days and comes with a guarantee",
    },
    "busy_mom": {
        "name": "Busy Mom",
        "age_range": "28–44",
        "gender": "Female",
        "income": "Medium",
        "platform_primary": ["tiktok", "facebook", "instagram"],
        "language_style": "time-saving focus, practical, relatable chaos, family-first",
        "vocab": ["mom hack", "game changer", "my kids love it", "saves me time", "easy",
                  "simple", "no more", "finally", "stress-free", "quick", "5 minutes",
                  "life saver", "found this and cried", "why didn't I know about this sooner"],
        "hook_triggers": ["saves time", "mom hack", "my kids", "easy", "simple"],
        "pain_points": ["no time", "kids making mess", "needing quick solutions", "wanting easy"],
        "buying_triggers": ["time savings", "kid-approved", "easy to use", "solves specific problem"],
        "objections": ["is it safe for kids", "is it easy to use", "is it fast"],
        "cta_style": "practical and helpful — 'link in bio, ships in 2 days'",
        "content_energy": "relatable, warm, 'finally someone gets it' energy",
        "example_hook": "This saved me 30 minutes every single morning and I genuinely cried",
        "example_cta": "Link in bio — order tonight and it's here by the weekend",
    },
    "fitness_focused": {
        "name": "Fitness & Health",
        "age_range": "18–38",
        "gender": "Any",
        "income": "Low–High",
        "platform_primary": ["tiktok", "instagram", "youtube"],
        "language_style": "results-oriented, transformation-focused, motivational",
        "vocab": ["gains", "transformation", "results", "game changer", "level up",
                  "before and after", "30 days", "actually works", "no more excuses",
                  "progress", "consistency", "worth it"],
        "hook_triggers": ["transformation", "results", "before/after", "actually works", "30 days"],
        "pain_points": ["slow results", "expensive gym", "inconsistency", "plateaus"],
        "buying_triggers": ["visible results", "specific timeframe", "social proof transformations"],
        "objections": ["will I actually see results", "how long does it take"],
        "cta_style": "motivational + urgency — 'link in bio, start your transformation today'",
        "content_energy": "energetic, motivational, proof-driven",
        "example_hook": "30 days of using this. Here's what actually happened.",
        "example_cta": "Link in bio — start yours today 💪",
    },
    "entrepreneur": {
        "name": "Entrepreneur / Side Hustler",
        "age_range": "22–42",
        "gender": "Any",
        "income": "Variable",
        "platform_primary": ["tiktok", "youtube", "instagram"],
        "language_style": "ROI-focused, efficiency-driven, business-minded",
        "vocab": ["ROI", "pays for itself", "saves time", "scales", "systems", "automation",
                  "invest in yourself", "worth it", "productive", "efficiency", "level up"],
        "hook_triggers": ["saves time", "pays for itself", "ROI", "makes more money"],
        "pain_points": ["wasted time", "inefficiency", "not scaling"],
        "buying_triggers": ["time ROI", "money ROI", "makes their life/business easier"],
        "objections": ["will it actually save time", "what's the real ROI"],
        "cta_style": "ROI framing — 'link in bio — pays for itself in a week'",
        "content_energy": "smart, efficient, no-fluff",
        "example_hook": "This paid for itself in 3 days. Here's how.",
        "example_cta": "Link in bio — this one's actually worth the investment",
    },
}


def _ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 60) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        if resp.ok:
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[Avatar] Ollama error: {e}")
    return ""


class AvatarEngine:

    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)

    def get_avatar(self, avatar_id: str) -> dict:
        return AVATARS.get(avatar_id, AVATARS["millennial_female"])

    def list_avatars(self) -> list:
        return [{"id": k, "name": v["name"], "age_range": v["age_range"],
                 "platforms": v["platform_primary"]} for k, v in AVATARS.items()]

    def get_avatars_for_niche(self, niche: str) -> list:
        """Return the most relevant avatar IDs for a given niche."""
        niche_map = {
            "beauty":  ["gen_z_female", "millennial_female", "budget_shopper", "premium_buyer"],
            "fitness": ["fitness_focused", "millennial_female", "budget_shopper", "busy_mom"],
            "home":    ["busy_mom", "millennial_female", "premium_buyer", "budget_shopper"],
            "tech":    ["entrepreneur", "gen_z_female", "millennial_female", "budget_shopper"],
            "pet":     ["busy_mom", "millennial_female", "budget_shopper", "gen_z_female"],
            "fashion": ["gen_z_female", "millennial_female", "budget_shopper", "premium_buyer"],
            "default": ["millennial_female", "gen_z_female", "budget_shopper", "busy_mom"],
        }
        return niche_map.get(niche.lower(), niche_map["default"])

    def generate_avatar_variant(
        self,
        base_content: str,
        avatar_id: str,
        content_type: str,
        product_name: str,
        platform: str,
    ) -> dict:
        """Rewrite base_content tuned specifically to this avatar's language and triggers."""
        avatar = self.get_avatar(avatar_id)

        # Load learned patterns for this avatar if available
        learned = self._load_learned_patterns(avatar_id)
        learned_hint = ""
        if learned.get("winning_hooks"):
            top_hooks = learned["winning_hooks"][:3]
            learned_hint = f"\nTop-performing hook patterns for this avatar:\n" + "\n".join(f"- {h}" for h in top_hooks)

        prompt = f"""You are an expert social media copywriter.
Rewrite this {content_type} for a very specific audience: {avatar['name']} ({avatar['age_range']}, {avatar['gender']}).

AUDIENCE PROFILE:
- Language style: {avatar['language_style']}
- Their vocabulary: {', '.join(avatar['vocab'][:8])}
- Hook triggers: {', '.join(avatar['hook_triggers'])}
- Main pain points: {', '.join(avatar['pain_points'])}
- Buying triggers: {', '.join(avatar['buying_triggers'])}
- CTA style: {avatar['cta_style']}
- Content energy: {avatar['content_energy']}

EXAMPLE HOOK FOR THIS AUDIENCE: "{avatar['example_hook']}"
EXAMPLE CTA FOR THIS AUDIENCE: "{avatar['example_cta']}"
{learned_hint}

RULES:
- Open with a hook that hits their specific trigger ({avatar['hook_triggers'][0]})
- Use their vocabulary naturally — not forced
- Address their #1 pain point: {avatar['pain_points'][0]}
- Close with their style of CTA
- Keep same platform format ({platform}) and approximate length
- Sound like a REAL {avatar['name']}, not a brand

PRODUCT: {product_name}

ORIGINAL CONTENT:
{base_content}

Output ONLY the rewritten content for this avatar. Nothing else."""

        result = _ollama(prompt, self.model)
        return {
            "avatar_id": avatar_id,
            "avatar_name": avatar["name"],
            "content": result if result else base_content,
            "platform": platform,
            "content_type": content_type,
            "product": product_name,
            "generated_by": "ollama" if result else "fallback",
        }

    def generate_all_avatar_variants(
        self,
        base_content: str,
        content_type: str,
        product_name: str,
        platform: str,
        niche: str = "default",
        max_avatars: int = 4,
    ) -> list:
        """Generate variants for all relevant avatars for this niche."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        avatar_ids = self.get_avatars_for_niche(niche)[:max_avatars]
        variants = []

        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {
                ex.submit(self.generate_avatar_variant, base_content, av_id, content_type, product_name, platform): av_id
                for av_id in avatar_ids
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    variants.append(result)

        return variants

    def _load_learned_patterns(self, avatar_id: str) -> dict:
        """Load avatar learned patterns from SQLite (falls back to old JSON file on first run)."""
        data = _ldb._sqlite_load(f"avatar_patterns:{avatar_id}")
        if data:
            return data
        # One-time migration: pull from old JSON file if it exists
        old_path = LEARNING_DIR / f"avatar_{avatar_id}.json"
        if old_path.exists():
            try:
                data = json.loads(old_path.read_text())
                _ldb._sqlite_store(f"avatar_patterns:{avatar_id}", data)
                old_path.rename(old_path.with_suffix(".json.migrated"))
                return data
            except:
                pass
        return {}

    def update_learned_patterns(self, avatar_id: str, winning_content: str, metric: str, value: float):
        """Called by LearningEngine when a variant wins. Updates this avatar's known winners in SQLite."""
        data = self._load_learned_patterns(avatar_id)

        first_line = winning_content.strip().split("\n")[0][:100]

        if metric == "ctr":
            hooks = data.get("winning_hooks", [])
            if first_line not in hooks:
                hooks.insert(0, first_line)
            data["winning_hooks"] = hooks[:10]

        elif metric == "conversion":
            converts = data.get("winning_converts", [])
            if first_line not in converts:
                converts.insert(0, first_line)
            data["winning_converts"] = converts[:10]

        data[f"best_{metric}"] = max(data.get(f"best_{metric}", 0.0), value)
        data["total_wins"] = data.get("total_wins", 0) + 1

        _ldb._sqlite_store(f"avatar_patterns:{avatar_id}", data)


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    engine = AvatarEngine()

    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        for av in engine.list_avatars():
            print(f"  {av['id']:25} {av['name']:20} {av['age_range']} — {', '.join(av['platforms'])}")

    elif len(sys.argv) >= 2 and sys.argv[1] == "test":
        base = "Stop scrolling — this glow serum is insane. I've been using it for 2 weeks and my skin is completely different. Link in bio."
        print("Generating variants for 'beauty' niche...\n")
        variants = engine.generate_all_avatar_variants(base, "instagram_caption", "Glow Serum", "instagram", "beauty")
        for v in variants:
            print(f"\n── {v['avatar_name']} ──────────────────")
            print(v['content'])
    else:
        print("Usage: python avatar_engine.py list")
        print("       python avatar_engine.py test")
