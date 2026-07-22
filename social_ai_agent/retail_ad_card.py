import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""Retail ad card generator — BUYER-facing product ads.

Unlike the old scorecard, this renders what a shopper wants to see:
real product photo, benefit headline, price + savings, SHOP NOW button.
No internal metrics ever appear here.
"""
import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1000, 1500
PHOTO_H = 880

TEAL = (6, 182, 164)
CORAL = (255, 82, 82)
DARK = (24, 28, 35)
GRAY = (110, 118, 130)
LIGHT = (248, 249, 251)
WHITE = (255, 255, 255)

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]
_FONT_REG_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def _font(size: int, bold: bool = True):
    for p in (_FONT_CANDIDATES if bold else _FONT_REG_CANDIDATES):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fetch_photo(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "image/*,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data))
        return img.convert("RGB")
    except Exception:
        return None


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale + center-crop to exactly w x h."""
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    img = img.resize((int(sw * scale) + 1, int(sh * scale) + 1), Image.LANCZOS)
    sw, sh = img.size
    left = (sw - w) // 2
    top = (sh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


BENEFIT_BY_HOOK = {
    "problem-solving": "The upgrade everyone wishes they'd bought sooner",
    "visual-demo": "See it once and you'll want one",
    "curiosity-hook": "The find everyone keeps asking about",
    "giftable": "The gift that actually gets used",
}
DEFAULT_BENEFIT = "Trending now — see what the fuss is about"


def generate_retail_ad(
    product_name: str,
    photo_url: str = "",
    retail_price: float = 0.0,
    compare_at: float = 0.0,
    hooks: list | None = None,
    buyer_quote: str = "",
    output_path: str = "ad_card.png",
    trending: bool = True,
    benefit_override: str = "",
) -> str | None:
    """Build a 1000x1500 buyer-facing ad card. Returns output path or None."""
    try:
        canvas = Image.new("RGB", (W, H), LIGHT)
        draw = ImageDraw.Draw(canvas)

        # ── Product photo (top) ──
        photo = _fetch_photo(photo_url)
        if photo is not None:
            canvas.paste(_cover(photo, W, PHOTO_H), (0, 0))
        else:
            # Fallback: soft gradient block with product initial
            grad = Image.new("RGB", (W, PHOTO_H), TEAL)
            gd = ImageDraw.Draw(grad)
            for y in range(PHOTO_H):
                t = y / PHOTO_H
                gd.line([(0, y), (W, y)], fill=(
                    int(6 + t * 40), int(182 - t * 60), int(164 - t * 20)))
            canvas.paste(grad, (0, 0))
            big = _font(220)
            initial = (product_name or "?")[0].upper()
            tw = draw.textlength(initial, font=big)
            draw = ImageDraw.Draw(canvas)
            draw.text(((W - tw) / 2, PHOTO_H / 2 - 140), initial, font=big, fill=WHITE)

        draw = ImageDraw.Draw(canvas)

        # "TRENDING NOW" pill on photo
        if trending:
            pill_f = _font(30)
            label = "TRENDING NOW"
            pw = draw.textlength(label, font=pill_f) + 44
            _rounded(draw, (36, 36, 36 + pw, 92), 28, CORAL)
            draw.text((36 + 22, 47), label, font=pill_f, fill=WHITE)

        # ── Bottom panel ──
        panel_top = PHOTO_H
        draw.rectangle((0, panel_top, W, H), fill=WHITE)

        y = panel_top + 38

        # Headline: product name
        h_font = _font(62)
        lines = _wrap(draw, product_name.title(), h_font, W - 120)[:2]
        for ln in lines:
            draw.text((60, y), ln, font=h_font, fill=DARK)
            y += 74

        # Benefit line: AI-written copy first, then real buyer quote, then template
        b_font = _font(33, bold=False)
        if benefit_override:
            benefit = benefit_override
        elif buyer_quote:
            benefit = f'“{buyer_quote}” — real buyer comment'
        else:
            benefit = DEFAULT_BENEFIT
            for h in (hooks or []):
                if h in BENEFIT_BY_HOOK:
                    benefit = BENEFIT_BY_HOOK[h]
                    break
        for ln in _wrap(draw, benefit, b_font, W - 120)[:2]:
            draw.text((60, y + 4), ln, font=b_font, fill=GRAY)
            y += 46
        y += 26

        # Price row
        if retail_price > 0:
            p_font = _font(84)
            price_txt = f"${retail_price:,.2f}"
            draw.text((60, y), price_txt, font=p_font, fill=DARK)
            px = 60 + draw.textlength(price_txt, font=p_font) + 30
            if compare_at > retail_price:
                c_font = _font(40, bold=False)
                cmp_txt = f"${compare_at:,.2f}"
                cy = y + 42
                draw.text((px, cy), cmp_txt, font=c_font, fill=GRAY)
                cw = draw.textlength(cmp_txt, font=c_font)
                draw.line((px, cy + 24, px + cw, cy + 24), fill=GRAY, width=4)
                save_pct = int(round((1 - retail_price / compare_at) * 100))
                s_font = _font(30)
                s_txt = f"SAVE {save_pct}%"
                sw = draw.textlength(s_txt, font=s_font) + 40
                _rounded(draw, (px + cw + 26, cy - 2, px + cw + 26 + sw, cy + 52), 26, CORAL)
                draw.text((px + cw + 26 + 20, cy + 8), s_txt, font=s_font, fill=WHITE)
            y += 112
        else:
            y += 10

        # CTA button
        cta_top = max(y + 8, H - 210)
        _rounded(draw, (60, cta_top, W - 60, cta_top + 104), 52, TEAL)
        cta_f = _font(46)
        cta = "SHOP NOW  →"
        cw = draw.textlength(cta, font=cta_f)
        draw.text(((W - cw) / 2, cta_top + 24), cta, font=cta_f, fill=WHITE)

        # Trust row (bullets — check glyphs missing from some Windows fonts)
        t_font = _font(27, bold=False)
        trust = "Secure checkout   •   Tracked delivery"
        tw = draw.textlength(trust, font=t_font)
        draw.text(((W - tw) / 2, cta_top + 128), trust, font=t_font, fill=GRAY)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(str(out), "PNG")
        return str(out)
    except Exception as e:
        print(f"[retail_ad_card] failed for {product_name}: {e}")
        return None


if __name__ == "__main__":
    p = generate_retail_ad(
        product_name="Anti Bark Trainer",
        photo_url="",
        retail_price=29.99,
        compare_at=44.99,
        hooks=["problem-solving"],
        output_path="test_retail_ad.png",
    )
    print(p)
