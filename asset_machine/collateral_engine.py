import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""Marketing Collateral Engine.

Takes what discovery gathered from the internet (product, photos, real buyer
language, trend signals) and runs it through the stored advisor playbooks —
Gary Vee (attention/native/raw), Alex Hormozi (value equation/offer/anchoring),
Kamil Sattar (ecom hooks/POV/test angles) — to produce OUR OWN collateral:

    10 distinct ad cards per product, all pointing at ONE sales page.

Copy: advisor-formula templates, upgraded by Quinn (local AI) when the bridge
is up. Visuals: 5 rotating layouts x rotating palettes so the 10 ads look like
they came from different creatives, per Kamil's multi-angle testing protocol.
"""
import os
import json
from pathlib import Path

import requests
from PIL import Image, ImageDraw

SHIPSTACK_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SHIPSTACK_ROOT))

from social_ai_agent.retail_ad_card import (  # noqa: E402
    _font, _fetch_photo, _cover, _wrap, _rounded, W, H,
)

ADVISORS_DIR = SHIPSTACK_ROOT / "agents" / "advisors"
QUINN_URL = os.getenv("QUINN_ENDPOINT", "http://127.0.0.1:8765")
QUINN_MODEL = os.getenv("SHIPSTACK_MODEL", "qwen2.5:7b")
# ALIEN = the GPU box. Copy generation runs there per Alex's standing order.
ALIEN_OLLAMA = os.getenv("ALIEN_OLLAMA_URL", "http://100.66.135.31:11434")
LOCAL_OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


def _ai_chat(prompt: str, max_tokens: int = 600, temperature: float = 0.85) -> str:
    """AI chain: Quinn bridge -> ALIEN Ollama (GPU) -> local Ollama -> ''.
    Short timeouts; never blocks a run for long."""
    # 1. Quinn bridge (the sanctioned router) — quick probe
    try:
        r = requests.post(f"{QUINN_URL}/v1/chat/completions", json={
            "model": QUINN_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": temperature,
        }, timeout=8)
        c = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
        if c:
            return c
    except Exception:
        pass
    # 2. ALIEN GPU, then local CPU
    for base in (ALIEN_OLLAMA, LOCAL_OLLAMA):
        try:
            r = requests.post(f"{base}/api/chat", json={
                "model": QUINN_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }, timeout=75)
            c = (r.json().get("message") or {}).get("content", "")
            if c:
                return c
        except Exception:
            continue
    return ""

WHITE = (255, 255, 255)
DARK = (24, 28, 35)
GRAY = (110, 118, 130)

# palette = (primary, accent, panel_bg, panel_text)
PALETTES = [
    ((6, 182, 164),  (255, 82, 82),   (255, 255, 255), (24, 28, 35)),    # teal/coral
    ((21, 44, 84),   (255, 176, 32),  (255, 255, 255), (24, 28, 35)),    # navy/amber
    ((34, 84, 61),   (240, 226, 194), (250, 248, 243), (30, 40, 34)),    # forest/cream
    ((74, 33, 84),   (255, 199, 44),  (255, 255, 255), (30, 24, 38)),    # plum/gold
    ((18, 18, 18),   (190, 242, 60),  (250, 250, 250), (18, 18, 18)),    # black/lime
]


def load_advisors() -> dict:
    """Load the stored marketer playbooks (the ShipStack workbook)."""
    out = {}
    for f in ADVISORS_DIR.glob("*.json"):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    return out


# ── Pain/benefit language derived from the product keyword ───────────────
PAIN_BY_TERM = {
    "bark": "the nonstop barking", "clean": "scrubbing for hours", "cleaner": "scrubbing for hours",
    "organizer": "the clutter", "storage": "the clutter", "posture": "back pain at your desk",
    "hair": "bad hair days", "pet": "pet messes", "dog": "dog chaos", "cat": "cat messes",
    "kitchen": "kitchen chaos", "garden": "yard work taking all weekend",
    "yard": "yard work taking all weekend", "wash": "paying for car washes",
    "washer": "paying for car washes", "light": "boring dark rooms", "lights": "boring dark rooms",
    "fitness": "gym memberships you never use", "sleep": "restless nights",
    "massage": "sore muscles", "charger": "dead batteries", "bottle": "buying plastic bottles",
    "fountain": "a boring backyard", "greenhouse": "plants dying every winter",
}
GENERIC_PAIN = "doing it the hard way"


def _pain_for(keyword: str, title: str = "") -> str:
    """Scan the keyword AND the real product title for pain language."""
    for source in (keyword, title):
        for tok in (source or "").lower().split():
            if tok in PAIN_BY_TERM:
                return PAIN_BY_TERM[tok]
    return GENERIC_PAIN


def build_copy_variants(product: dict) -> list[dict]:
    """10 ad copy variants from the advisor formulas. Uses REAL gathered data:
    product name, buyer quotes, signal counts, price."""
    name = product.get("title", "This find")
    kw = product.get("keyword", "")
    price = product.get("retail_price", 0)
    compare = product.get("compare_at", 0)
    quote = (product.get("intent") or [""])[0]
    n_signals = product.get("n_signals", 0)
    pain = _pain_for(kw, name)
    cat = kw or "home"

    v = [
        # ── Hormozi: dream outcome (value equation) ──
        dict(archetype="hormozi_dream", advisor="Hormozi",
             headline=f"Never deal with {pain} again",
             subline=f"{name} handles it — set it up once, done.",
             cta="SHOP NOW", badge="TRENDING NOW"),
        # ── Hormozi: offer anchor ──
        dict(archetype="hormozi_offer", advisor="Hormozi",
             headline=f"${compare:,.0f} value. ${price:,.2f} today.",
             subline="30-day returns. If it's not for you, send it back.",
             cta="CLAIM THIS PRICE", badge=f"SAVE {int(round((1-price/compare)*100)) if compare>price>0 else 30}%"),
        # ── Hormozi: stop doing X ──
        dict(archetype="hormozi_stop", advisor="Hormozi",
             headline=f"Stop {pain}. Do this instead.",
             subline=f"{name} — the fix people wish they'd found sooner.",
             cta="SEE HOW", badge="NEW WAY"),
        # ── Hormozi: the secret ──
        dict(archetype="hormozi_secret", advisor="Hormozi",
             headline=f"The {cat} upgrade nobody told you about",
             subline="Specific, simple, and it just works.",
             cta="SHOP NOW", badge="INSIDER FIND"),
        # ── Kamil: POV hook ──
        dict(archetype="kamil_pov", advisor="Kamil",
             headline=f"POV: you finally fixed {pain}",
             subline=f"{name} — going viral for a reason.",
             cta="GET YOURS", badge="AS SEEN ON SOCIAL"),
        # ── Kamil: we tested them all ──
        dict(archetype="kamil_tested", advisor="Kamil",
             headline=f"We compared the top {cat} finds. This one won.",
             subline="Real product, real results — see for yourself.",
             cta="SEE THE WINNER", badge="TOP PICK"),
        # ── Kamil: why is nobody talking ──
        dict(archetype="kamil_viral", advisor="Kamil",
             headline="Why is nobody talking about this?",
             subline=f"{name}, quietly selling out at ${price:,.2f}.",
             cta="SHOP BEFORE IT'S GONE", badge="UNDER THE RADAR"),
        # ── Gary Vee: hot take ──
        dict(archetype="garyvee_hot", advisor="GaryVee",
             headline="Unpopular opinion: skip the big-brand version",
             subline=f"This does the same job for ${price:,.2f}.",
             cta="JUDGE FOR YOURSELF", badge="HOT TAKE"),
        # ── Gary Vee: question caption ──
        dict(archetype="garyvee_question", advisor="GaryVee",
             headline="Would you use this?",
             subline=f"{name} — tap and decide in 10 seconds.",
             cta="TAKE A LOOK", badge="YOU DECIDE"),
        # ── Proof + direct (specificity sells) ──
        dict(archetype="proof_direct", advisor="Hormozi",
             headline=(f'"{quote}" — real buyer' if quote
                       else f"{max(n_signals, 2)} people talking about this right now"),
             subline=f"{name} · ${price:,.2f} with tracked delivery.",
             cta="SHOP NOW", badge="BUYER APPROVED"),
    ]
    return v


def juice_with_ai(product: dict, variants: list[dict]) -> list[dict]:
    """Sharpen every headline/subline in the advisors' voices via the AI chain
    (Quinn bridge -> ALIEN GPU -> local). Bad output -> keep formula copy."""
    name = product.get("title", "")
    kw = product.get("keyword", "")
    listing = "\n".join(f'{i+1}. [{v["archetype"]}] {v["headline"]} | {v["subline"]}'
                        for i, v in enumerate(variants))
    content = _ai_chat(
        f"You are a direct-response copy chief trained on Gary Vee, Alex Hormozi "
        f"and Kamil Sattar. Product: '{name}' ({kw}). Improve each ad line below — "
        f"keep the same angle, make it punchier, max 9 words per headline, max 12 per subline. "
        f"No emojis. Reply ONLY with numbered lines: N. headline | subline\n\n{listing}"
    )
    for ln in content.splitlines():
        ln = ln.strip()
        if not ln or "." not in ln[:4] or "|" not in ln:
            continue
        try:
            idx = int(ln.split(".", 1)[0]) - 1
            rest = ln.split(".", 1)[1]
            head, sub = [x.strip().strip('"') for x in rest.split("|", 1)]
            # Store as CANDIDATES — the grader decides later whether the AI
            # version actually beats the formula version.
            if 0 <= idx < len(variants) and 3 < len(head) < 90:
                variants[idx]["ai_headline"] = head
                if 3 < len(sub) < 120:
                    variants[idx]["ai_subline"] = sub
        except Exception:
            continue
    return variants


# ── Product-specific AI copy (guru-INFLUENCED, not guru-copied) ──────────
# Each archetype carries the advisor's PRINCIPLE. The AI applies the
# principle to THIS product — it must not parrot the principle's wording.
PRINCIPLES = {
    "hormozi_dream":   "Hormozi's value equation — lead with the dream outcome this exact product delivers; paint the after-state vividly",
    "hormozi_offer":   "Hormozi's grand slam offer — anchor the higher price, reveal the deal, stack the value, kill risk with the 30-day guarantee",
    "hormozi_stop":    "Hormozi's pattern interrupt — tell them to stop the old painful way and position this product as the obvious replacement",
    "hormozi_secret":  "curiosity plus specificity — frame this product as the insider find and hint one concrete benefit",
    "kamil_pov":       "Kamil's POV hook — a first-person moment where this product just solved the problem",
    "kamil_tested":    "Kamil's testing angle — we compared the options and THIS one won for one concrete reason",
    "kamil_viral":     "Kamil's under-the-radar angle — why is nobody talking about this product yet",
    "garyvee_hot":     "Gary Vee's hot take — a bold, slightly polarizing opinion about this product vs the mainstream option",
    "garyvee_question": "Gary Vee's engagement rule — ask the buyer one direct question that makes them picture using it",
    "proof_direct":    "specificity sells — use real buyer words or a concrete number, then a direct offer",
}


def ai_copy_set(product: dict, archetypes: list[str]) -> dict:
    """Generate ORIGINAL, product-specific copy for the given archetypes.
    Returns {index: (headline, subline)} for lines the AI produced well."""
    name = product.get("title", "")
    kw = product.get("keyword", "")
    price = product.get("retail_price", 0)
    compare = product.get("compare_at", 0)
    quote = (product.get("intent") or [""])[0]
    supplier = product.get("supplier_title", "")

    briefs = "\n".join(
        f"{i+1}. Angle: {PRINCIPLES.get(a, a)}"
        for i, a in enumerate(archetypes)
    )
    quote_line = f'A real buyer comment about it: "{quote}". ' if quote else ""
    content = _ai_chat(
        f"You write scroll-stopping retail ads. THE PRODUCT: '{name}'"
        f"{f' (full listing: {supplier})' if supplier else ''}, category: {kw}. "
        f"Price ${price:,.2f}, compared at ${compare:,.2f}. {quote_line}"
        f"Write one ad per numbered angle below. The copy must be SPECIFIC to what this "
        f"product physically is and does — mention the product or its concrete benefit, "
        f"never generic filler like 'doing it the hard way'. Do not quote or repeat the "
        f"angle description itself. NEVER mention any marketer's name (no Hormozi, Kamil, "
        f"Gary Vee) — buyers must never see them. No emojis, no hype words like revolutionary.\n\n{briefs}\n\n"
        f"Reply ONLY with numbered lines, one per angle, format:\n"
        f"N. headline (max 9 words) | subline (max 14 words)",
        max_tokens=700, temperature=0.9,
    )
    out = {}
    for ln in content.splitlines():
        ln = ln.strip()
        if not ln or "." not in ln[:4] or "|" not in ln:
            continue
        try:
            idx = int(ln.split(".", 1)[0]) - 1
            rest = ln.split(".", 1)[1]
            head, sub = [x.strip().strip('"') for x in rest.split("|", 1)]
            if 0 <= idx < len(archetypes) and len(head.split()) >= 4:
                out[idx] = (head[:90], sub[:140])
        except Exception:
            continue
    return out


def ai_retry_copy(product: dict, archetype: str, rejected: dict,
                  existing_headlines: list[str]) -> tuple[str, str]:
    """Context-injected retry for ONE ad the user didn't like.
    The AI gets: the guru principle, the rejected ad, and every OTHER ad we
    already have (so it doesn't repeat any of them). Returns (head, sub) or ('','')."""
    name = product.get("title", "")
    kw = product.get("keyword", "")
    price = product.get("retail_price", 0)
    compare = product.get("compare_at", 0)
    quote = (product.get("intent") or [""])[0]
    others = "\n".join(f"- {h}" for h in existing_headlines[:9]) or "- (none)"
    quote_line = f'Real buyer comment: "{quote}". ' if quote else ""

    content = _ai_chat(
        f"You are retrying ONE rejected ad. THE PRODUCT: '{name}' ({kw}), "
        f"${price:,.2f} (compare ${compare:,.2f}). {quote_line}\n"
        f"THE ANGLE to apply (from the marketing gurus): {PRINCIPLES.get(archetype, archetype)}\n\n"
        f"THE USER REJECTED THIS VERSION — do something clearly different:\n"
        f"  headline: {rejected.get('headline','')}\n  subline: {rejected.get('subline','')}\n\n"
        f"ADS WE ALREADY HAVE — do NOT resemble any of these:\n{others}\n\n"
        f"Write ONE new ad. Specific to this product, fresh wording, no generic filler, "
        f"no emojis, and NEVER mention any marketer's name (no Hormozi, Kamil, Gary Vee). "
        f"Reply with exactly one line:\nHEADLINE: ... | SUB: ...",
        max_tokens=120, temperature=0.95,
    )
    for ln in content.splitlines():
        ln = ln.strip()
        if "|" in ln:
            ln = ln.replace("HEADLINE:", "").replace("SUB:", "")
            try:
                head, sub = [x.strip().strip('"') for x in ln.split("|", 1)]
                if len(head.split()) >= 4:
                    return head[:90], sub[:140]
            except Exception:
                continue
    return "", ""


def build_photo_pool(product: dict, limit: int = 12) -> list[str]:
    """Gather DIFFERENT product images from supplier search — by product title
    first (best match), then by category keyword. Unique, ordered."""
    from discovery_engine.suppliers import cj_dropshipping
    urls = []
    seen = set()
    queries = []
    title = product.get("title", "")
    if title:
        queries.append(" ".join(title.split()[:4]))
    kw = product.get("keyword", "")
    if kw and kw.lower() not in (q.lower() for q in queries):
        queries.append(kw)
    for q in queries:
        try:
            for listing in cj_dropshipping.search(q, limit=10):
                u = listing.get("image") or ""
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
                if len(urls) >= limit:
                    return urls
        except Exception:
            continue
    # Always include the currently known photo as a fallback member
    cur = product.get("photo_url", "")
    if cur and cur not in seen:
        urls.append(cur)
    return urls


# ── The Grader: custom weighting from the Hormozi + Gary Vee playbooks ───
# Every piece of copy gets scored before it ships. Weights per Alex's spec:
# offer strength is king ($100M Offers), then emotion + problem-solving,
# then CTA clarity, then logic/specificity.
GRADE_WEIGHTS = {
    "offer_strength": 0.30,   # anchor, savings, guarantee, value stack
    "emotional": 0.20,        # pain/dream language, 'you', vivid outcome
    "problem_solution": 0.20, # names the pain AND presents the mechanism
    "cta_clarity": 0.15,      # one clear imperative action
    "logical": 0.15,          # numbers, specificity — 'specificity sells'
}

_EMOTION_WORDS = ["never", "finally", "tired", "hate", "love", "wish", "stop",
                  "again", "deal with", "chaos", "mess", "pain", "free", "easy",
                  "sick of", "goodbye", "dream", "feel", "worry", "stress"]
_PROBLEM_WORDS = ["fix", "fixed", "solve", "solves", "solution", "handles",
                  "stop", "never", "instead", "no more", "without", "ends"]
_CTA_VERBS = ["shop", "get", "claim", "grab", "see", "try", "tap", "buy",
              "take", "judge", "decide", "order"]
_RISK_REVERSAL = ["return", "returns", "guarantee", "money back", "risk-free",
                  "send it back", "30-day"]


def grade_copy(copy: dict, product: dict) -> dict:
    """Score one ad's copy 0-100 with the custom advisor weighting.
    Returns {scores, total, letter, advice}."""
    text = f"{copy.get('headline','')} {copy.get('subline','')}".lower()
    cta = (copy.get("cta") or "").lower()
    price = product.get("retail_price", 0)
    compare = product.get("compare_at", 0)
    advice = []

    # Emotional (Hormozi: paint the after; Gary Vee: real reactions)
    emo_hits = sum(1 for w in _EMOTION_WORDS if w in text)
    has_you = "you" in text.split() or "your" in text
    emotional = min(1.0, emo_hits * 0.3 + (0.3 if has_you else 0))
    if emotional < 0.5:
        advice.append("Add pain or dream-outcome language (Hormozi: paint the after)")

    # Logical / specificity ("'47 customers' beats 'many customers'")
    import re as _re
    numbers = len(_re.findall(r"[\$\d]", text))
    logical = min(1.0, numbers * 0.12)
    if logical < 0.4:
        advice.append("Add specifics — a number, a price, a timeframe")

    # Problem -> solution (Kamil POD: problem, outcome, demo)
    prob_hits = sum(1 for w in _PROBLEM_WORDS if w in text)
    problem_solution = min(1.0, prob_hits * 0.35)
    if problem_solution < 0.4:
        advice.append("Name the problem and position the product as THE fix")

    # CTA clarity (one imperative, no options)
    cta_clarity = 0.0
    if any(v in cta for v in _CTA_VERBS):
        cta_clarity = 0.8
        if len(cta.split()) <= 4:
            cta_clarity = 1.0
    else:
        advice.append("CTA needs one clear action verb")

    # Offer strength ($100M Offers: anchor high, stack value, reverse risk)
    offer = 0.0
    if compare > price > 0:
        offer += 0.35                      # price anchor exists
    if "$" in text:
        offer += 0.2                       # price shown in copy
    if any(w in text for w in _RISK_REVERSAL):
        offer += 0.3                       # risk reversal
    if any(w in text for w in ["value", "includes", "free", "bonus", "today"]):
        offer += 0.15                      # value stack / urgency framing
    offer = min(1.0, offer)
    if offer < 0.5:
        advice.append("Strengthen the offer: anchor the price, add the guarantee")

    scores = {
        "emotional": round(emotional, 2),
        "logical": round(logical, 2),
        "problem_solution": round(problem_solution, 2),
        "cta_clarity": round(cta_clarity, 2),
        "offer_strength": round(offer, 2),
    }
    total = round(sum(scores[k] * GRADE_WEIGHTS[k] for k in GRADE_WEIGHTS) * 100)
    letter = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D"
    return {"scores": scores, "total": total, "letter": letter, "advice": advice}


def improve_offer(copy: dict, product: dict, grade: dict) -> dict:
    """Auto-apply Hormozi fixes to weak copy — make the offer one people
    don't want to refuse. Then it gets re-graded."""
    price = product.get("retail_price", 0)
    compare = product.get("compare_at", 0)
    sub = copy.get("subline", "")
    scores = grade["scores"]

    if scores["offer_strength"] < 0.6:
        add = []
        if not any(w in sub.lower() for w in _RISK_REVERSAL):
            add.append("30-day returns")
        if compare > price > 0 and "$" not in f"{copy.get('headline','')} {sub}":
            add.append(f"${price:,.2f} (was ${compare:,.0f})")
        if add:
            sub = (sub.rstrip(". ") + ". " + " · ".join(add))[:140]
            copy["subline"] = sub

    if scores["cta_clarity"] < 0.8:
        copy["cta"] = "SHOP NOW"
    return copy


# ── Rendering: 5 layouts ─────────────────────────────────────────────────

def _price_block(draw, x, y, price, compare, accent, text_color):
    if price <= 0:
        return y
    p_font = _font(72)
    txt = f"${price:,.2f}"
    draw.text((x, y), txt, font=p_font, fill=text_color)
    px = x + draw.textlength(txt, font=p_font) + 24
    if compare > price:
        c_font = _font(34, bold=False)
        cmp_txt = f"${compare:,.2f}"
        cy = y + 34
        draw.text((px, cy), cmp_txt, font=c_font, fill=GRAY)
        cw = draw.textlength(cmp_txt, font=c_font)
        draw.line((px, cy + 22, px + cw, cy + 22), fill=GRAY, width=4)
    return y + 96


def _cta_button(draw, y, cta, primary, width_pad=60):
    _rounded(draw, (width_pad, y, W - width_pad, y + 100), 50, primary)
    f = _font(42)
    tw = draw.textlength(cta + "  →", font=f)
    draw.text(((W - tw) / 2, y + 26), cta + "  →", font=f, fill=WHITE)
    return y + 100


def _badge_pill(draw, x, y, label, accent):
    f = _font(28)
    pw = draw.textlength(label, font=f) + 40
    _rounded(draw, (x, y, x + pw, y + 52), 26, accent)
    draw.text((x + 20, y + 10), label, font=f, fill=WHITE)


def render_variant(product: dict, copy: dict, layout: int, palette_i: int,
                   out_path: str, photo: Image.Image | None) -> str | None:
    """Render one ad card. layout 0-4, distinct composition each."""
    primary, accent, panel_bg, panel_text = PALETTES[palette_i % len(PALETTES)]
    price = product.get("retail_price", 0)
    compare = product.get("compare_at", 0)
    try:
        canvas = Image.new("RGB", (W, H), panel_bg)
        draw = ImageDraw.Draw(canvas)

        if layout == 0:
            # Classic: photo top 55%, panel bottom
            ph = 830
            if photo: canvas.paste(_cover(photo, W, ph), (0, 0))
            else: draw.rectangle((0, 0, W, ph), fill=primary)
            draw.rectangle((0, ph, W, H), fill=panel_bg)
            draw = ImageDraw.Draw(canvas)
            _badge_pill(draw, 36, 36, copy["badge"], accent)
            y = ph + 42
            for ln in _wrap(draw, copy["headline"], _font(58), W - 120)[:2]:
                draw.text((60, y), ln, font=_font(58), fill=panel_text); y += 70
            for ln in _wrap(draw, copy["subline"], _font(32, bold=False), W - 120)[:2]:
                draw.text((60, y + 4), ln, font=_font(32, bold=False), fill=GRAY); y += 44
            y = _price_block(draw, 60, y + 20, price, compare, accent, panel_text)
            _cta_button(draw, max(y + 10, H - 170), copy["cta"], primary)

        elif layout == 1:
            # Full-bleed photo + dark gradient overlay
            if photo: canvas.paste(_cover(photo, W, H), (0, 0))
            else: draw.rectangle((0, 0, W, H), fill=primary)
            grad = Image.new("L", (1, H))
            for yy in range(H):
                t = max(0, (yy - H * 0.38) / (H * 0.62))
                grad.putpixel((0, yy), int(215 * t))
            overlay = Image.new("RGB", (W, H), (8, 10, 14))
            canvas.paste(overlay, (0, 0), grad.resize((W, H)))
            draw = ImageDraw.Draw(canvas)
            _badge_pill(draw, 36, 36, copy["badge"], accent)
            y = H - 560
            for ln in _wrap(draw, copy["headline"], _font(64), W - 120)[:2]:
                draw.text((60, y), ln, font=_font(64), fill=WHITE); y += 78
            for ln in _wrap(draw, copy["subline"], _font(33, bold=False), W - 120)[:2]:
                draw.text((60, y), ln, font=_font(33, bold=False), fill=(210, 216, 226)); y += 46
            if price > 0:
                pf = _font(70); ptxt = f"${price:,.2f}"
                draw.text((60, y + 14), ptxt, font=pf, fill=WHITE)
                if compare > price:
                    _badge_pill(draw, 60 + int(draw.textlength(ptxt, font=pf)) + 26, y + 30,
                                f"WAS ${compare:,.0f}", accent)
                y += 110
            _cta_button(draw, H - 150, copy["cta"], primary)

        elif layout == 2:
            # Color block top with headline, photo bottom
            bh = 600
            draw.rectangle((0, 0, W, bh), fill=primary)
            y = 90
            _badge_pill(draw, 60, y - 54, copy["badge"], accent)
            y = 150
            for ln in _wrap(draw, copy["headline"], _font(66), W - 120)[:3]:
                draw.text((60, y), ln, font=_font(66), fill=WHITE); y += 80
            for ln in _wrap(draw, copy["subline"], _font(32, bold=False), W - 120)[:2]:
                draw.text((60, y + 6), ln, font=_font(32, bold=False), fill=(235, 238, 245)); y += 44
            if photo: canvas.paste(_cover(photo, W, H - bh - 160), (0, bh))
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, H - 160, W, H), fill=panel_bg)
            if price > 0:
                pf = _font(56)
                draw.text((60, H - 138), f"${price:,.2f}", font=pf, fill=panel_text)
            _rounded(draw, (W - 470, H - 138, W - 60, H - 42), 48, accent)
            f2 = _font(36); tw = draw.textlength(copy["cta"], font=f2)
            draw.text((W - 470 + (410 - tw) / 2, H - 110), copy["cta"], font=f2, fill=WHITE)

        elif layout == 3:
            # Minimal: headline top, rounded photo center, price+CTA below
            y = 70
            _badge_pill(draw, 60, y - 10, copy["badge"], accent)
            y = 150
            for ln in _wrap(draw, copy["headline"], _font(60), W - 120)[:2]:
                draw.text((60, y), ln, font=_font(60), fill=panel_text); y += 74
            py = y + 24
            ph = 760
            if photo:
                img = _cover(photo, W - 120, ph)
                mask = Image.new("L", img.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), 36, fill=255)
                canvas.paste(img, (60, py), mask)
            else:
                _rounded(draw, (60, py, W - 60, py + ph), 36, primary)
            draw = ImageDraw.Draw(canvas)
            y = py + ph + 30
            for ln in _wrap(draw, copy["subline"], _font(31, bold=False), W - 120)[:1]:
                draw.text((60, y), ln, font=_font(31, bold=False), fill=GRAY); y += 46
            y = _price_block(draw, 60, y + 6, price, compare, accent, panel_text)
            _cta_button(draw, max(y, H - 150), copy["cta"], primary)

        else:
            # Bold: photo top, dark panel with light text
            ph2 = 800
            if photo: canvas.paste(_cover(photo, W, ph2), (0, 0))
            else: draw.rectangle((0, 0, W, ph2), fill=primary)
            dark_panel = (16, 20, 28) if palette_i % len(PALETTES) != 4 else (18, 18, 18)
            draw.rectangle((0, ph2, W, H), fill=dark_panel)
            draw = ImageDraw.Draw(canvas)
            _badge_pill(draw, 36, ph2 - 78, copy["badge"], accent)
            y = ph2 + 46
            for ln in _wrap(draw, copy["headline"], _font(58), W - 120)[:2]:
                draw.text((60, y), ln, font=_font(58), fill=WHITE); y += 70
            for ln in _wrap(draw, copy["subline"], _font(31, bold=False), W - 120)[:2]:
                draw.text((60, y + 4), ln, font=_font(31, bold=False), fill=(170, 178, 190)); y += 44
            if price > 0:
                draw.text((60, y + 14), f"${price:,.2f}", font=_font(66), fill=accent); y += 100
            _cta_button(draw, max(y, H - 160), copy["cta"], accent)

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(str(out), "PNG")
        return str(out)
    except Exception as e:
        print(f"[collateral] render failed ({copy.get('archetype')}): {e}")
        return None


def generate_collateral_set(product: dict, out_dir: str, n: int = 10,
                            use_ai: bool = True, progress_cb=None) -> list[dict]:
    """The engine: gathered internet data in -> 10 graded, original ad cards out.

    Flow: advisor formulas -> AI juice (ALIEN GPU) -> Hormozi grade ->
    auto-improve weak offers -> re-grade -> rank best-first -> render.
    Returns [{path, headline, subline, cta, archetype, advisor, grade, letter}]."""
    if progress_cb:
        try: progress_cb("writing 10 ad angles from the advisor playbooks")
        except Exception: pass
    variants = build_copy_variants(product)[:n]

    if use_ai:
        if progress_cb:
            try: progress_cb("ALIEN GPU is punching up the copy")
            except Exception: pass
        variants = juice_with_ai(product, variants)

    # AI-vs-formula playoff: the grader referees. The AI rewrite only ships
    # if it grades at least as high AND reads like a real sentence (5+ words).
    for v in variants:
        if v.get("ai_headline") and len(v["ai_headline"].split()) >= 5:
            cand = dict(v)
            cand["headline"] = v["ai_headline"]
            cand["subline"] = v.get("ai_subline") or v["subline"]
            if grade_copy(cand, product)["total"] >= grade_copy(v, product)["total"]:
                v["headline"] = cand["headline"]
                v["subline"] = cand["subline"]
                v["juiced"] = True
        v.pop("ai_headline", None)
        v.pop("ai_subline", None)

    # Grade every piece, auto-fix weak offers, re-grade, rank best first
    for v in variants:
        g = grade_copy(v, product)
        if g["total"] < 70:
            v = improve_offer(v, product, g)
            g = grade_copy(v, product)
        v["grade"] = g["total"]
        v["letter"] = g["letter"]
        v["grade_detail"] = g["scores"]
        v["advice"] = g["advice"]
    variants.sort(key=lambda v: v.get("grade", 0), reverse=True)

    # Fetch the product photo ONCE, reuse across all renders
    photo = _fetch_photo(product.get("photo_url", "")) if product.get("photo_url") else None

    results = []
    pid = product.get("product_id", "product")[:28]
    for i, copy in enumerate(variants):
        if progress_cb:
            try: progress_cb(f"rendering ad {i+1} of {len(variants)} (grade {copy.get('letter','?')})")
            except Exception: pass
        path = str(Path(out_dir) / f"{pid}_v{i+1}.png")
        res = render_variant(product, copy, layout=i % 5, palette_i=i % len(PALETTES),
                             out_path=path, photo=photo)
        if res:
            results.append({"path": res, "headline": copy["headline"],
                            "subline": copy.get("subline", ""), "cta": copy.get("cta", ""),
                            "archetype": copy["archetype"], "advisor": copy["advisor"],
                            "grade": copy.get("grade", 0), "letter": copy.get("letter", "?")})
    return results


if __name__ == "__main__":
    demo = {"product_id": "demo_washer", "title": "High-Pressure Car Wash Gun",
            "keyword": "car wash", "retail_price": 36.99, "compare_at": 55.99,
            "intent": ["worth it"], "n_signals": 12, "photo_url": ""}
    out = generate_collateral_set(demo, str(SHIPSTACK_ROOT / "pinterest_cards" / "demo"), use_ai=False)
    print(json.dumps([{k: v for k, v in r.items() if k != "path"} for r in out], indent=2))
    print(f"{len(out)} cards rendered")
