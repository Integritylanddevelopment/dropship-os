"""
content_qa.py — Content Quality Assurance Engine for ShipStack
=============================================================
Scores every piece of content on 5 dimensions before it goes out.
Auto-rewrites anything that fails. Uses Ollama (free, local).

Scoring dimensions (each 0–10, total 50):
  1. Hook Strength     — Does it stop the scroll in 2 seconds?
  2. Value Clarity     — Hormozi: is the dream outcome unmistakable?
  3. CTA Power         — Is the ask obvious, urgent, frictionless?
  4. Platform Fit      — Right format/length/energy for TikTok/IG/YT?
  5. Conversion Intent — Would a warm lead actually click and buy?

Thresholds:
  ≥ 40  → PASS (auto-schedule)
  30–39 → REVIEW (human approval queue)
  < 30  → FAIL (auto-rewrite, max 3 attempts)
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

OLLAMA_URL   = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

BASE_DIR = Path(__file__).parent.parent

# ── Platform rules reference ─────────────────────────────────────────────────
PLATFORM_RULES = {
    "tiktok": {
        "max_caption_chars": 2200,
        "ideal_caption_chars": (150, 400),
        "hook_must_be_first": True,
        "needs_cta": True,
        "ideal_hashtags": (3, 8),
        "energy": "high",
        "note": "Hook must land in first 3 words. POD structure. Post 7am/12pm/8pm CT.",
    },
    "instagram": {
        "max_caption_chars": 2200,
        "ideal_caption_chars": (100, 300),
        "hook_must_be_first": True,
        "needs_cta": True,
        "ideal_hashtags": (5, 15),
        "energy": "medium-high",
        "note": "Jab/jab/right-hook. First line visible before 'more'. Save-worthy content.",
    },
    "youtube": {
        "max_caption_chars": 5000,
        "ideal_caption_chars": (200, 600),
        "hook_must_be_first": False,
        "needs_cta": True,
        "ideal_hashtags": (2, 5),
        "energy": "informative",
        "note": "SEO keywords in first 100 chars. Include timestamps. Value-first.",
    },
    "ad_hook": {
        "max_caption_chars": 150,
        "ideal_caption_chars": (30, 100),
        "hook_must_be_first": True,
        "needs_cta": True,
        "ideal_hashtags": (0, 0),
        "energy": "ultra-high",
        "note": "Pattern interrupt. Must create curiosity gap. 3-sec rule is everything.",
    },
}

# ── Quick rule-based checks (no Ollama) ─────────────────────────────────────
STRONG_HOOK_SIGNALS = [
    "pov:", "stop scrolling", "nobody talks", "i tested", "honest review",
    "why is nobody", "this changed", "i can't believe", "wait", "don't buy",
    "obsessed", "viral", "secret", "hack", "broke", "insane",
]

WEAK_HOOK_SIGNALS = [
    "hello", "hi everyone", "today i want", "in this video", "welcome",
    "let me show", "check out", "introducing", "new product",
]

CTA_SIGNALS = [
    "link in bio", "comment", "save", "share", "tag", "click", "shop",
    "grab", "swipe", "dm me", "follow", "subscribe",
]

HORMOZI_VALUE_SIGNALS = [
    # Dream outcome words
    "transform", "change", "finally", "results", "work", "actually",
    "proven", "guarantee", "without", "even if", "days", "minutes",
]


def _ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 45) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        if resp.ok:
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[QA] Ollama error: {e}")
    return ""


# ── Scoring functions ────────────────────────────────────────────────────────

def score_hook(text: str, platform: str) -> dict:
    """Score the opening hook. Quick rule-based + optional Ollama boost."""
    first_line = text.strip().split("\n")[0][:120].lower()
    score = 5  # baseline

    # Strong signals → +points
    for sig in STRONG_HOOK_SIGNALS:
        if sig in first_line:
            score += 1.5
            break

    # Weak signals → -points
    for sig in WEAK_HOOK_SIGNALS:
        if sig in first_line:
            score -= 2
            break

    # Length check — short first lines punch harder on mobile
    if len(first_line) <= 60:
        score += 1
    elif len(first_line) > 100:
        score -= 1

    # Question → curiosity gap
    if "?" in first_line:
        score += 0.5

    # Power words
    power_words = ["secret", "free", "banned", "exposed", "warning", "finally", "stop"]
    if any(w in first_line for w in power_words):
        score += 1

    score = max(0, min(10, score))
    grade = "strong" if score >= 7 else "average" if score >= 4 else "weak"
    return {"score": round(score, 1), "grade": grade, "first_line": first_line[:80]}


def score_value_clarity(text: str) -> dict:
    """Hormozi Value Equation: Dream Outcome × Likelihood / (Time × Effort)"""
    text_lower = text.lower()
    score = 5

    # Dream outcome present?
    dream_words = ["results", "transform", "change", "lose", "gain", "save", "make", "get", "feel", "look", "become"]
    if any(w in text_lower for w in dream_words):
        score += 1.5

    # Specificity → builds belief
    has_numbers = bool(re.search(r"\d+", text))
    if has_numbers:
        score += 1.5

    # Time compression ("in 7 days", "overnight", "instantly")
    time_words = ["days", "hours", "week", "overnight", "instantly", "fast", "quick", "minutes"]
    if any(w in text_lower for w in time_words):
        score += 1

    # Effort reduction ("without", "no gym", "even if you", "just")
    effort_words = ["without", "no need", "even if", "just", "easy", "simple", "no experience"]
    if any(w in text_lower for w in effort_words):
        score += 1

    # Vague fluff → -points
    vague = ["great", "amazing product", "must have", "check it out", "really good", "awesome"]
    if any(w in text_lower for w in vague):
        score -= 1.5

    score = max(0, min(10, score))
    grade = "compelling" if score >= 7 else "average" if score >= 4 else "vague"
    return {"score": round(score, 1), "grade": grade}


def score_cta(text: str, platform: str) -> dict:
    """Score the call-to-action."""
    text_lower = text.lower()
    score = 3  # start low — no CTA is a big problem

    has_cta = False
    for sig in CTA_SIGNALS:
        if sig in text_lower:
            has_cta = True
            score += 3
            break

    if not has_cta:
        return {"score": 2, "grade": "missing", "has_cta": False}

    # Urgency → better
    urgency_words = ["now", "today", "before it sells out", "limited", "ends", "hurry", "last chance"]
    if any(w in text_lower for w in urgency_words):
        score += 2

    # Specific ask (comment word, reply with) → very high conversion
    specific = ["comment '", "reply with", "dm me", "comment below with"]
    if any(w in text_lower for w in specific):
        score += 2

    # Frictionless (link in bio vs. "go to website and search...")
    if "link in bio" in text_lower or "bio" in text_lower:
        score += 1

    score = max(0, min(10, score))
    grade = "strong" if score >= 7 else "adequate" if score >= 4 else "weak"
    return {"score": round(score, 1), "grade": grade, "has_cta": True}


def score_platform_fit(text: str, platform: str, content_type: str) -> dict:
    """Check platform-specific rules."""
    rules = PLATFORM_RULES.get(platform, PLATFORM_RULES["tiktok"])
    score = 6  # baseline — assume decent fit
    issues = []

    char_count = len(text)
    min_chars, max_chars = rules["ideal_caption_chars"]

    if char_count < min_chars:
        score -= 2
        issues.append(f"Too short ({char_count} chars, ideal {min_chars}-{max_chars})")
    elif char_count > rules["max_caption_chars"]:
        score -= 3
        issues.append(f"Too long ({char_count} chars, max {rules['max_caption_chars']})")
    elif min_chars <= char_count <= max_chars:
        score += 1

    # Hashtag check
    hashtags = len(re.findall(r"#\w+", text))
    h_min, h_max = rules["ideal_hashtags"]
    if h_min <= hashtags <= h_max:
        score += 1
    elif hashtags > h_max + 5:
        score -= 1
        issues.append(f"Too many hashtags ({hashtags})")
    elif platform != "ad_hook" and hashtags < h_min:
        score -= 0.5
        issues.append(f"Too few hashtags ({hashtags})")

    # Emoji presence (expected on TikTok/IG)
    has_emoji = bool(re.search(r"[\U0001F300-\U0001FFFF]", text))
    if platform in ("tiktok", "instagram") and not has_emoji:
        score -= 1
        issues.append("Missing emojis (expected for this platform)")

    score = max(0, min(10, score))
    grade = "great fit" if score >= 7 else "acceptable" if score >= 4 else "poor fit"
    return {"score": round(score, 1), "grade": grade, "issues": issues, "char_count": char_count}


def score_conversion_intent(text: str, product_name: str) -> dict:
    """Will a warm lead actually click and buy? Rule-based + Ollama sentiment."""
    text_lower = text.lower()
    score = 5

    # Product mentioned
    if product_name.lower() in text_lower:
        score += 1

    # Social proof signals
    proof_words = ["reviews", "people", "customers", "sold", "rated", "love", "obsessed", "k sold", "stars"]
    if any(w in text_lower for w in proof_words):
        score += 1.5

    # Scarcity/FOMO
    fomo_words = ["selling out", "limited", "only", "last", "almost gone", "selling fast", "before it's gone"]
    if any(w in text_lower for w in fomo_words):
        score += 1.5

    # Benefit over feature (features: "has", "made of", "includes" vs benefits: "makes you", "gives you", "helps you")
    benefits = ["makes you", "gives you", "helps you", "feel", "look", "become", "get rid of", "finally"]
    features = ["includes", "made of", "comes with", "features", "has the", "material"]
    benefit_count = sum(1 for w in benefits if w in text_lower)
    feature_count = sum(1 for w in features if w in text_lower)
    if benefit_count > feature_count:
        score += 1
    elif feature_count > benefit_count + 1:
        score -= 1

    # Price anchoring or value framing
    if any(w in text_lower for w in ["worth", "value", "save", "compared to", "instead of"]):
        score += 0.5

    score = max(0, min(10, score))
    grade = "high intent" if score >= 7 else "moderate" if score >= 4 else "low intent"
    return {"score": round(score, 1), "grade": grade}


# ── AI-powered improvement ───────────────────────────────────────────────────

def ai_improve(text: str, weak_areas: list, platform: str, product_name: str) -> str:
    """Ask Ollama to fix specific weak areas in the content."""
    issues_str = "\n".join(f"- {a}" for a in weak_areas)
    prompt = f"""You are an expert social media copywriter and conversion specialist.
Fix the following {platform} content for the product "{product_name}".

SPECIFIC ISSUES TO FIX:
{issues_str}

RULES:
- Keep the same length and platform format
- Make the hook land in the FIRST 3 words
- Include a specific, urgent CTA
- Add concrete numbers or results if missing
- Sound natural and human — not corporate
- Benefits over features always

ORIGINAL CONTENT:
{text}

Output ONLY the improved version, nothing else."""

    result = _ollama(prompt)
    return result if result and len(result) > 30 else text


# ── Main QA class ────────────────────────────────────────────────────────────

class ContentQA:

    def __init__(self, model: str = OLLAMA_MODEL, auto_fix: bool = True, max_fix_attempts: int = 3):
        self.model = model
        self.auto_fix = auto_fix
        self.max_fix_attempts = max_fix_attempts

    def score(self, content: str, content_type: str, platform: str, product_name: str, niche: str = "default") -> dict:
        """Score a single piece of content. Returns full QA report."""

        # Determine text to score (script vs caption vs description)
        text = content
        if isinstance(content, dict):
            text = content.get("script") or content.get("caption") or content.get("description") or content.get("hook") or str(content)

        # Run all 5 scores
        hook    = score_hook(text, platform)
        value   = score_value_clarity(text)
        cta     = score_cta(text, platform)
        fit     = score_platform_fit(text, platform, content_type)
        convert = score_conversion_intent(text, product_name)

        total = hook["score"] + value["score"] + cta["score"] + fit["score"] + convert["score"]

        # Determine verdict
        if total >= 40:
            verdict = "PASS"
        elif total >= 30:
            verdict = "REVIEW"
        else:
            verdict = "FAIL"

        # Identify weak areas for feedback
        weak_areas = []
        if hook["score"] < 6:
            weak_areas.append(f"Weak hook ({hook['grade']}) — first line doesn't grab attention")
        if value["score"] < 6:
            weak_areas.append(f"Vague value ({value['grade']}) — dream outcome unclear, add numbers/specifics")
        if cta["score"] < 6:
            weak_areas.append(f"Weak CTA ({cta['grade']}) — {'missing entirely' if not cta.get('has_cta') else 'not urgent or specific enough'}")
        if fit["score"] < 6:
            for issue in fit.get("issues", []):
                weak_areas.append(f"Platform issue: {issue}")
        if convert["score"] < 6:
            weak_areas.append(f"Low conversion intent ({convert['grade']}) — add social proof, FOMO, or benefits")

        return {
            "verdict": verdict,
            "total_score": round(total, 1),
            "max_score": 50,
            "percentage": round(total / 50 * 100, 1),
            "scores": {
                "hook":       hook,
                "value":      value,
                "cta":        cta,
                "platform_fit": fit,
                "conversion": convert,
            },
            "weak_areas": weak_areas,
            "text_preview": text[:120] + "..." if len(text) > 120 else text,
            "platform": platform,
            "content_type": content_type,
        }

    def qa_and_fix(self, content: str, content_type: str, platform: str, product_name: str, niche: str = "default") -> dict:
        """Score content. If it fails, auto-rewrite until it passes or max attempts reached."""
        current_text = content
        history = []

        for attempt in range(1, self.max_fix_attempts + 1):
            report = self.score(current_text, content_type, platform, product_name, niche)
            report["attempt"] = attempt
            history.append(report)

            if report["verdict"] in ("PASS", "REVIEW"):
                break

            if not self.auto_fix or attempt >= self.max_fix_attempts:
                break

            # Auto-fix using Ollama
            print(f"    [QA] Attempt {attempt} failed ({report['total_score']}/50) — rewriting…")
            improved = ai_improve(current_text, report["weak_areas"], platform, product_name)
            if improved and improved != current_text:
                current_text = improved
            else:
                break  # Ollama didn't improve — stop trying

        final_report = history[-1]
        final_report["final_text"] = current_text
        final_report["attempts"] = len(history)
        final_report["improvement_history"] = [
            {"attempt": h["attempt"], "score": h["total_score"], "verdict": h["verdict"]}
            for h in history
        ]

        return final_report

    def qa_batch(self, variations: list, content_type: str, platform: str, product_name: str,
                 niche: str = "default", workers: int = 4) -> dict:
        """
        QA a batch of content variations in parallel.
        Returns stats + categorized results (pass/review/fail).
        """
        results = {"pass": [], "review": [], "fail": [], "stats": {}}
        total = len(variations)
        print(f"[QA] Running QA on {total} {platform} {content_type} pieces…")

        def _check_one(item):
            text = item.get("script") or item.get("caption") or item.get("description") or item.get("hook") or str(item)
            report = self.qa_and_fix(text, content_type, platform, product_name, niche)
            item["qa"] = report
            item["qa_score"] = report["total_score"]
            item["qa_verdict"] = report["verdict"]
            item["final_text"] = report.get("final_text", text)
            return item

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_check_one, v): i for i, v in enumerate(variations)}
            for future in as_completed(futures):
                item = future.result()
                verdict = item["qa_verdict"]
                results[verdict.lower()].append(item)

        # Sort each bucket by score descending
        for bucket in ("pass", "review", "fail"):
            results[bucket].sort(key=lambda x: x["qa_score"], reverse=True)

        pass_count   = len(results["pass"])
        review_count = len(results["review"])
        fail_count   = len(results["fail"])

        results["stats"] = {
            "total": total,
            "pass": pass_count,
            "review": review_count,
            "fail": fail_count,
            "pass_rate": round(pass_count / total * 100, 1) if total else 0,
            "avg_score": round(
                sum(v["qa_score"] for bucket in results.values() if isinstance(bucket, list) for v in bucket) / total, 1
            ) if total else 0,
            "top_scorer": results["pass"][0]["qa_score"] if results["pass"] else 0,
        }

        print(f"[QA] Results: {pass_count} pass | {review_count} review | {fail_count} fail | avg {results['stats']['avg_score']}/50")
        return results

    def taste_test(self, spin_results: dict, sample_size: int = 10) -> dict:
        """
        Quick taste test: pull a random sample from spin results,
        run full QA, return a human-readable report.
        Good for spot-checking before a big batch.
        """
        import random
        report = {"product": spin_results.get("product"), "samples": [], "summary": {}}

        for platform, variations in spin_results.get("spins", {}).items():
            if not variations:
                continue
            sample = random.sample(variations, min(sample_size, len(variations)))
            content_type = {"tiktok": "tiktok_script", "instagram": "instagram_caption",
                            "youtube": "youtube_description", "ad_hooks": "ad_hook"}.get(platform, platform)

            platform_name = platform if platform != "ad_hooks" else "ad_hook"
            qa_batch = self.qa_batch(sample, content_type, platform_name,
                                     spin_results.get("product", "Product"),
                                     spin_results.get("niche", "default"), workers=2)
            report["samples"].append({
                "platform": platform,
                "sample_size": len(sample),
                "stats": qa_batch["stats"],
                "top_3": qa_batch["pass"][:3] + qa_batch["review"][:1],
            })

        # Overall pass rate
        all_pass = sum(s["stats"]["pass"] for s in report["samples"])
        all_total = sum(s["stats"]["total"] for s in report["samples"])
        report["summary"] = {
            "overall_pass_rate": round(all_pass / all_total * 100, 1) if all_total else 0,
            "recommendation": (
                "Ready to schedule" if all_pass / all_total >= 0.7 else
                "Review failures before scheduling" if all_pass / all_total >= 0.4 else
                "Significant rewrites needed — check your Quinn output"
            ) if all_total else "No samples",
        }

        return report


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    qa = ContentQA(auto_fix=True)

    if len(sys.argv) >= 2 and sys.argv[1] == "taste-test":
        # python content_qa.py taste-test data/product_collateral/product_slug/spins.json
        if len(sys.argv) < 3:
            print("Usage: python content_qa.py taste-test <spins.json>")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            spins = json.load(f)
        report = qa.taste_test(spins, sample_size=5)
        print(json.dumps(report, indent=2))

    elif len(sys.argv) >= 2 and sys.argv[1] == "score":
        # python content_qa.py score "your content here" tiktok "Product Name"
        text = sys.argv[2] if len(sys.argv) > 2 else "Test content"
        platform = sys.argv[3] if len(sys.argv) > 3 else "tiktok"
        product = sys.argv[4] if len(sys.argv) > 4 else "Product"
        result = qa.qa_and_fix(text, "tiktok_script", platform, product)
        print(f"\nVerdict : {result['verdict']}")
        print(f"Score   : {result['total_score']}/50 ({result['percentage']}%)")
        for dim, data in result["scores"].items():
            print(f"  {dim:16}: {data['score']}/10  ({data.get('grade','—')})")
        if result["weak_areas"]:
            print(f"\nIssues:")
            for w in result["weak_areas"]:
                print(f"  • {w}")
        if result.get("final_text") != text:
            print(f"\nImproved version:\n{result['final_text']}")

    else:
        print("Usage:")
        print('  python content_qa.py score "your content" tiktok "ProductName"')
        print("  python content_qa.py taste-test path/to/spins.json")
