"""
content_spinner.py — Content Scale Engine for ShipStack
Takes one Quinn-generated script/caption and spins it into dozens of
variations using Ollama (local, free, no API cost).

Spin targets per product push:
  TikTok scripts     : base 3 × 50 = 150 unique scripts
  Instagram captions : base 3 × 40 = 120
  YouTube descriptions: base 2 × 30 = 60
  Ad hooks           : base 5 × 20 = 100
  Total per product  : ~430 unique pieces
"""

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Optional
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

OLLAMA_URL = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")   # fast, small — perfect for spinning

BASE_DIR = Path(__file__).parent.parent


# ── Hook formulas (rotate through 10) ────────────────────────────────────────
HOOK_FORMULAS = [
    "POV: you just discovered {product}",
    "I tested {product} so you don't have to",
    "Nobody talks about this but {product} actually works",
    "Stop scrolling — {product} changed everything for me",
    "The {product} hack that went viral (and it actually works)",
    "Why is nobody talking about {product}?",
    "I was today years old when I found out about {product}",
    "This {product} has {followers}k people obsessed",
    "Honest review: {product} after 30 days",
    "Wait till you see what {product} does",
]

# ── CTAs (rotate through 5) ──────────────────────────────────────────────────
CTAS = [
    "Link in bio — grab yours before it sells out 🔗",
    "Comment 'INFO' and I'll send you the link",
    "Save this post so you don't lose it ❤️",
    "Tag someone who NEEDS this",
    "Shop the link in my bio before the sale ends",
]

# ── Emoji sets per niche ──────────────────────────────────────────────────────
EMOJI_SETS = {
    "beauty":    ["✨", "💄", "🌸", "💅", "🪞", "💆‍♀️"],
    "fitness":   ["💪", "🏋️", "🔥", "⚡", "🥇", "🏃"],
    "home":      ["🏡", "✨", "🪴", "🛋️", "🧹", "💫"],
    "tech":      ["📱", "⚡", "🤖", "💻", "🔧", "🚀"],
    "pet":       ["🐾", "🐶", "🐱", "❤️", "🦴", "😍"],
    "fashion":   ["👗", "✨", "💃", "👠", "🛍️", "💋"],
    "default":   ["✨", "🔥", "💯", "⚡", "🎯", "💫"],
}

# ── Caption structure templates ───────────────────────────────────────────────
CAPTION_STRUCTURES = [
    "{hook}\n\n{body}\n\n{cta}",
    "{hook} {emoji}\n\n{body}\n\n{cta}",
    "{hook}\n\n{body}\n\n{cta} {emoji}",
    "{body}\n\n{hook}\n\n{cta}",
    "{hook}\n\n{cta}\n\n{body}",
]


def _ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 30) -> str:
    """Call Ollama local API. Returns generated text or original on failure."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        if resp.ok:
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[Spinner] Ollama error: {e}")
    return ""


def _get_emojis(niche: str, count: int = 2) -> str:
    pool = EMOJI_SETS.get(niche.lower(), EMOJI_SETS["default"])
    return " ".join(random.sample(pool, min(count, len(pool))))


def _fill_hook(template: str, product_name: str, extra: dict = None) -> str:
    subs = {"product": product_name, "followers": random.randint(50, 500)}
    if extra:
        subs.update(extra)
    try:
        return template.format(**subs)
    except KeyError:
        return template


class ContentSpinner:

    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model

    def _rewrite(self, text: str, style_hint: str = "") -> str:
        """Ask Ollama to lightly rewrite text to create a variation."""
        prompt = (
            f"Rewrite this social media content slightly differently. "
            f"Keep the same meaning and length. Sound natural and human. "
            f"{style_hint}"
            f"Only output the rewritten version, nothing else.\n\n{text}"
        )
        result = _ollama(prompt, self.model)
        return result if result and len(result) > 20 else text

    def spin(
        self,
        base_content: str,
        product_name: str,
        num_variations: int = 50,
        content_type: str = "tiktok_script",
        niche: str = "default",
        style_hints: Optional[list] = None,
    ) -> list[dict]:
        """
        Spin base_content into num_variations unique pieces.
        Returns list of variation dicts.
        """
        variations = []
        styles = style_hints or [
            "Make it more casual and Gen-Z.",
            "Make it sound more excited and energetic.",
            "Make it sound more like a genuine personal review.",
            "Use a storytelling angle.",
            "Make it punchy and short.",
        ]

        for i in range(num_variations):
            hook = _fill_hook(random.choice(HOOK_FORMULAS), product_name)
            cta = random.choice(CTAS)
            emoji = _get_emojis(niche)
            style = styles[i % len(styles)]

            if content_type == "tiktok_script":
                variation = self._spin_tiktok(base_content, hook, cta, emoji, style, i)
            elif content_type == "instagram_caption":
                variation = self._spin_instagram(base_content, hook, cta, emoji, style, i)
            elif content_type == "youtube_description":
                variation = self._spin_youtube(base_content, hook, cta, emoji, style, i)
            elif content_type == "ad_hook":
                variation = self._spin_ad_hook(base_content, product_name, hook, emoji, style, i)
            else:
                variation = self._spin_generic(base_content, hook, cta, emoji, style, i)

            variation["variation_index"] = i + 1
            variation["content_type"] = content_type
            variation["product"] = product_name
            variation["niche"] = niche
            variations.append(variation)

            # Small delay to not hammer Ollama
            if i % 5 == 4:
                time.sleep(0.5)

        return variations

    def _spin_tiktok(self, base, hook, cta, emoji, style, idx) -> dict:
        if idx % 3 == 0:
            # Ollama rewrite
            body = self._rewrite(base, style)
        else:
            # Template-only variation (fast, no Ollama)
            body = base

        structure = random.choice(CAPTION_STRUCTURES)
        caption = structure.format(hook=hook, body=body, cta=cta, emoji=emoji)

        return {
            "script": body,
            "caption": caption,
            "hook": hook,
            "cta": cta,
            "method": "ollama" if idx % 3 == 0 else "template",
        }

    def _spin_instagram(self, base, hook, cta, emoji, style, idx) -> dict:
        if idx % 4 == 0:
            body = self._rewrite(base, style)
        else:
            body = base

        caption = f"{hook} {emoji}\n\n{body}\n\n.\n.\n.\n{cta}"
        return {
            "caption": caption,
            "hook": hook,
            "cta": cta,
            "method": "ollama" if idx % 4 == 0 else "template",
        }

    def _spin_youtube(self, base, hook, cta, emoji, style, idx) -> dict:
        if idx % 2 == 0:
            body = self._rewrite(base, style)
        else:
            body = base

        description = f"{hook}\n\n{body}\n\n{cta}\n\n#shorts #viral {emoji}"
        return {
            "description": description,
            "hook": hook,
            "cta": cta,
            "method": "ollama" if idx % 2 == 0 else "template",
        }

    def _spin_ad_hook(self, base, product, hook, emoji, style, idx) -> dict:
        short_hooks = [
            f"This {product} is insane {emoji}",
            f"Nobody expected {product} to actually work",
            f"I can't believe {product} is legal",
            f"{product} just broke the internet {emoji}",
            f"Don't buy {product} until you watch this",
        ]
        ad_hook = short_hooks[idx % len(short_hooks)]

        if idx % 5 == 0:
            body = self._rewrite(base, f"Make it a 15-second ad script. {style}")
        else:
            body = base[:200] if len(base) > 200 else base

        return {
            "hook": ad_hook,
            "body": body,
            "method": "ollama" if idx % 5 == 0 else "template",
        }

    def _spin_generic(self, base, hook, cta, emoji, style, idx) -> dict:
        body = self._rewrite(base, style) if idx % 3 == 0 else base
        return {
            "content": f"{hook}\n\n{body}\n\n{cta} {emoji}",
            "method": "ollama" if idx % 3 == 0 else "template",
        }

    # ── High-level: spin all content types for a product ─────────────────────
    def spin_product(
        self,
        quinn_output: dict,
        product_name: str,
        niche: str = "default",
        profile_count: int = 1,
    ) -> dict:
        """
        Takes Quinn's full content output and spins all content types.
        Returns a complete spin_results dict with total post count.

        With profile_count=10:
          150 TikTok scripts × 10 profiles = 1,500 posts
        """
        print(f"[Spinner] Starting spin for '{product_name}' ({niche}) — {profile_count} profiles")

        results = {
            "product": product_name,
            "niche": niche,
            "profile_count": profile_count,
            "spins": {},
            "totals": {},
        }

        # TikTok scripts — base 3 × 50 variations = 150
        tiktok_base = quinn_output.get("tiktok_scripts", [])
        if not isinstance(tiktok_base, list):
            tiktok_base = [tiktok_base]
        tiktok_variations = []
        for base in tiktok_base[:3]:
            if isinstance(base, dict):
                base = base.get("script", str(base))
            tiktok_variations += self.spin(base, product_name, 50, "tiktok_script", niche)
        results["spins"]["tiktok"] = tiktok_variations
        results["totals"]["tiktok_scripts"] = len(tiktok_variations)
        results["totals"]["tiktok_posts_with_profiles"] = len(tiktok_variations) * profile_count
        print(f"  TikTok: {len(tiktok_variations)} scripts → ×{profile_count} profiles = {len(tiktok_variations)*profile_count} posts")

        # Instagram captions — base 3 × 40 = 120
        ig_base = quinn_output.get("ig_captions", [])
        if not isinstance(ig_base, list):
            ig_base = [ig_base]
        ig_variations = []
        for base in ig_base[:3]:
            if isinstance(base, dict):
                base = base.get("caption", str(base))
            ig_variations += self.spin(base, product_name, 40, "instagram_caption", niche)
        results["spins"]["instagram"] = ig_variations
        results["totals"]["instagram_captions"] = len(ig_variations)
        results["totals"]["instagram_posts_with_profiles"] = len(ig_variations) * profile_count
        print(f"  Instagram: {len(ig_variations)} captions → ×{profile_count} = {len(ig_variations)*profile_count} posts")

        # YouTube descriptions — base 2 × 30 = 60
        yt_base = quinn_output.get("youtube_descriptions", [])
        if not isinstance(yt_base, list):
            yt_base = [yt_base]
        yt_variations = []
        for base in yt_base[:2]:
            if isinstance(base, dict):
                base = base.get("description", str(base))
            yt_variations += self.spin(base, product_name, 30, "youtube_description", niche)
        results["spins"]["youtube"] = yt_variations
        results["totals"]["youtube_descriptions"] = len(yt_variations)
        results["totals"]["youtube_posts_with_profiles"] = len(yt_variations) * profile_count
        print(f"  YouTube: {len(yt_variations)} descriptions → ×{profile_count} = {len(yt_variations)*profile_count} posts")

        # Ad hooks — base 5 × 20 = 100
        hook_base = quinn_output.get("hook_variants", [])
        if not isinstance(hook_base, list):
            hook_base = [hook_base]
        ad_variations = []
        for base in hook_base[:5]:
            if isinstance(base, dict):
                base = base.get("hook", str(base))
            ad_variations += self.spin(base, product_name, 20, "ad_hook", niche)
        results["spins"]["ad_hooks"] = ad_variations
        results["totals"]["ad_hooks"] = len(ad_variations)
        print(f"  Ad hooks: {len(ad_variations)} variations")

        # Grand total
        total_unique = (
            results["totals"]["tiktok_scripts"]
            + results["totals"]["instagram_captions"]
            + results["totals"]["youtube_descriptions"]
            + results["totals"]["ad_hooks"]
        )
        total_with_profiles = (
            results["totals"]["tiktok_posts_with_profiles"]
            + results["totals"]["instagram_posts_with_profiles"]
            + results["totals"]["youtube_posts_with_profiles"]
            + results["totals"]["ad_hooks"]
        )
        results["totals"]["unique_pieces"] = total_unique
        results["totals"]["total_posts_with_profiles"] = total_with_profiles

        print(f"\n[Spinner] DONE — {total_unique} unique pieces | {total_with_profiles} total posts across {profile_count} profiles")
        return results

    def save(self, spin_results: dict, output_dir: Optional[str] = None) -> str:
        """Save spin results to data/product_collateral/<slug>/spins.json"""
        slug = spin_results["product"].lower().replace(" ", "_")
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = BASE_DIR / "data" / "product_collateral" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "spins.json"
        out_path.write_text(json.dumps(spin_results, indent=2))
        print(f"[Spinner] Saved to {out_path}")
        return str(out_path)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python content_spinner.py <product_name> <quinn_output.json> [niche] [profile_count]")
        sys.exit(1)

    product_name = sys.argv[1]
    quinn_file   = sys.argv[2]
    niche        = sys.argv[3] if len(sys.argv) > 3 else "default"
    profiles     = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    with open(quinn_file) as f:
        quinn_output = json.load(f)

    spinner = ContentSpinner()
    results = spinner.spin_product(quinn_output, product_name, niche, profiles)
    spinner.save(results)

    print("\n── TOTALS ──────────────────────────────────")
    for k, v in results["totals"].items():
        print(f"  {k:40}: {v:,}")
