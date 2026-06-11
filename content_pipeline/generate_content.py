#!/usr/bin/env python3
"""
content_pipeline/generate_content.py — Ollama Content Generator
Reads decisions.json, uses qwen2.5:7b via local Ollama to generate
platform-specific content for the top 3 combos.
Gary Vee playbook: volume, hooks, repurposing.

Usage:
    cd "C:\Users\integ\Documents\Claude\Projects\ShipStack"
    python content_pipeline/generate_content.py

    # Generate for a specific product:
    python content_pipeline/generate_content.py --product "Automatic Pet Feeder" --niche "pet accessories"

    # Skip Ollama, use templates only (no AI needed):
    python content_pipeline/generate_content.py --templates-only
"""

import json
import argparse
import sys
import random
from datetime import datetime
from pathlib import Path

import os
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

import requests

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = Path(__file__).parent

_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1")
_OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_HOST = f"http://{_OLLAMA_HOST}:{_OLLAMA_PORT}"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Gary Vee hook formulas
HOOK_TEMPLATES = {
    "problem": [
        "POV: Your {niche} problem just got solved in 30 seconds",
        "Stop wasting money on {niche} that doesn't work",
        "Nobody talks about this {niche} hack",
        "I tried 12 {niche} products. This one actually works.",
    ],
    "social_proof": [
        "This {product} has 47K 5-star reviews and nobody talks about it",
        "{count} people bought this {product} last month. I finally tried it.",
        "Amazon reviewers are obsessed with this ${price} {product}",
        "My {niche} problem is gone after 3 years. Here's what fixed it.",
    ],
    "before_after": [
        "Before: {niche} nightmare. After: $29 fix. Let me show you.",
        "I spent 3 months trying to fix my {niche}. This did it in a week.",
        "The {product} I wish I bought 2 years ago",
        "Day 1 vs Day 30 using the {product}",
    ],
    "curiosity": [
        "This {product} is why my {niche} life changed forever",
        "The {niche} item everyone is buying but nobody is posting about",
        "Rate this {niche} find out of 10 👇",
        "Wait until you see what this {product} does",
    ],
}

PLATFORM_SPECS = {
    "tiktok": {
        "max_caption_len": 150,
        "hashtag_count": 5,
        "video_length": "15-30s",
        "tone": "casual, energetic, fast-paced",
        "cta": "Link in bio to grab yours",
    },
    "pinterest": {
        "max_caption_len": 500,
        "hashtag_count": 10,
        "format": "static pin or idea pin",
        "tone": "inspirational, descriptive, keyword-rich",
        "cta": "Save this pin + click to shop",
    },
    "instagram": {
        "max_caption_len": 300,
        "hashtag_count": 8,
        "video_length": "30-60s reel",
        "tone": "lifestyle, aspirational",
        "cta": "Link in bio 🔗",
    },
    "youtube_shorts": {
        "max_caption_len": 100,
        "hashtag_count": 3,
        "video_length": "under 60s",
        "tone": "educational, demonstrative",
        "cta": "Subscribe for more finds",
    },
}


def ollama_generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        return None


def is_ollama_running() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        models = [m["name"] for m in resp.json().get("models", [])]
        return any(OLLAMA_MODEL.split(":")[0] in m for m in models)
    except Exception:
        return False


def fill_template(template: str, product: str, niche: str, price: float = 29.99) -> str:
    return (template
        .replace("{product}", product)
        .replace("{niche}", niche)
        .replace("{price}", str(price))
        .replace("{count}", str(random.randint(8000, 47000)))
    )


def generate_for_platform(product: str, niche: str, platform: str,
                           price: float = 29.99, use_ollama: bool = True) -> dict:
    spec = PLATFORM_SPECS[platform]

    # Pick hook template
    hook_type = random.choice(list(HOOK_TEMPLATES.keys()))
    hook = fill_template(random.choice(HOOK_TEMPLATES[hook_type]), product, niche, price)

    if use_ollama:
        prompt = f"""You are a viral {platform} content creator. Gary Vee style: high energy, authentic, value-first.

Product: {product}
Niche: {niche}
Price: ${price:.2f}
Platform: {platform}
Tone: {spec['tone']}
Max caption length: {spec['max_caption_len']} chars
Hashtag count: {spec['get('hashtag_count', 5)]}
CTA: {spec['cta']}
Hook to use: {hook}

Write ONLY the caption/description text with hashtags. No explanations. Keep it under {spec['max_caption_len']} characters."""

        # Fix the f-string issue
        prompt = prompt.replace("spec['get('hashtag_count', 5)']", str(spec.get('hashtag_count', 5)))

        ai_text = ollama_generate(prompt)
    else:
        ai_text = None

    if ai_text:
        caption = ai_text
    else:
        # Template fallback
        cta = spec["cta"]
        niche_tags = niche.replace(" ", "").lower()
        product_tags = product.replace(" ", "").lower()
        hashtags_list = [f"#{niche_tags}", f"#{product_tags}", "#dropshipping", "#deals", "#viral"]
        hashtags = " ".join(hashtags_list[:spec.get("hashtag_count", 5)])
        caption = f"{hook}\n\n{cta}\n\n{hashtags}"

    return {
        "platform": platform,
        "product": product,
        "niche": niche,
        "hook_type": hook_type,
        "hook": hook,
        "caption": caption,
        "generated_by": "ollama" if (use_ollama and ai_text) else "template",
        "video_length": spec.get("video_length", ""),
        "cta": spec["cta"],
    }


def load_top_combos() -> list:
    decisions_path = BASE_DIR / "decisions.json"
    if decisions_path.exists():
        data = json.loads(decisions_path.read_text())
        return data.get("top_combos", [])[:3]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", type=str, default=None)
    parser.add_argument("--niche", type=str, default=None)
    parser.add_argument("--templates-only", action="store_true")
    parser.add_argument("--platforms", type=str, default="tiktok,pinterest,instagram,youtube_shorts")
    args = parser.parse_args()

    print("=" * 60)
    print("  CONTENT PIPELINE — Ollama × Gary Vee")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    use_ollama = not args.templates_only
    if use_ollama:
        if is_ollama_running():
            print(f"\n🤖 Ollama online — using {OLLAMA_MODEL}")
        else:
            print(f"\n⚠️  Ollama offline — falling back to templates")
            use_ollama = False

    platforms = [p.strip() for p in args.platforms.split(",")]

    if args.product:
        combos = [{"product": args.product, "niche": args.niche or "general", "profit_per_unit": 15}]
    else:
        combos = load_top_combos()
        if not combos:
            print("[ContentPipeline] No decisions.json. Run decision_engine.py first.")
            sys.exit(1)

    all_content = []
    for combo in combos:
        product = combo["product"]
        niche = combo["niche"]
        price = 29.99  # default

        print(f"\n📝 Generating for: {product} ({niche})")
        product_content = {"product": product, "niche": niche, "platforms": {}}

        for platform in platforms:
            content = generate_for_platform(product, niche, platform, price, use_ollama)
            product_content["platforms"][platform] = content
            print(f"   ✅ {platform}: [{content['generated_by']}] {content['hook'][:60]}...")

        all_content.append(product_content)

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_used": OLLAMA_MODEL if use_ollama else "templates",
        "combos_generated": len(all_content),
        "content": all_content,
    }

    out_path = OUTPUT_DIR / "content_batch.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Content batch saved → {out_path}")
    print(f"   {len(all_content)} products × {len(platforms)} platforms = {len(all_content) * len(platforms)} pieces")
    print("\nNext: Run post_scheduler.py to queue these for posting.\n")


if __name__ == "__main__":
    main()
