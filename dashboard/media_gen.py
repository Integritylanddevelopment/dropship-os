"""Stage 5 media kit generator. Calls Quinn bridge (Ollama) for ad copy + pollinations.ai for hero image."""
import json, re, urllib.parse, urllib.request
from datetime import datetime

QUINN_BRIDGE = "http://127.0.0.1:8765/v1/chat/completions"
IMG_BASE = "https://image.pollinations.ai/prompt/"
MODEL = "qwen2.5:7b"
PROMETHEUS_URL = "http://127.0.0.1:8766"

PROMPT_TPL = (
    "You are a short-form ad copywriter. For the product keyword '{kw}', return a strict JSON object "
    "with these keys: hook (one TikTok hook, exactly 12 words), caption (one product caption, exactly 30 words), "
    "hashtags (array of 5 lowercase hashtag strings each starting with #). "
    "Output ONLY the JSON object, no preface, no code fences."
)


def _call_llm(kw, timeout=60):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT_TPL.format(kw=kw)}],
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        QUINN_BRIDGE,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8", errors="replace"))
    text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return _parse_copy(text)


def _parse_copy(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    raw = m.group(0) if m else text
    try:
        obj = json.loads(raw)
    except Exception:
        return {"hook": text[:120], "caption": text[:240], "hashtags": []}
    hook = str(obj.get("hook", "")).strip()
    caption = str(obj.get("caption", "")).strip()
    tags = obj.get("hashtags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[\s,]+", tags) if t.strip()]
    tags = [("#" + t.lstrip("#")).lower() for t in tags if t][:5]
    return {"hook": hook, "caption": caption, "hashtags": tags}


def _image_url(kw):
    prompt = f"{kw} product hero shot vertical, studio lighting, ecommerce, high detail"
    return f"{IMG_BASE}{urllib.parse.quote(prompt)}?width=720&height=1280&nologo=true"


def generate_kit(product_keyword, supplier, auto_produce=False, platforms=None):
    kw = (product_keyword or "").strip()
    out = {
        "product_keyword": kw,
        "hook": "",
        "caption": "",
        "hashtags": [],
        "image_url": _image_url(kw or "product"),
        "supplier_price": None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if supplier and isinstance(supplier, dict):
        out["supplier_price"] = supplier.get("unit_cost")
        out["supplier_title"] = (supplier.get("title") or "")[:120]
        out["supplier_url"] = supplier.get("url") or ""
    try:
        copy = _call_llm(kw)
        out["hook"] = copy.get("hook", "")
        out["caption"] = copy.get("caption", "")
        out["hashtags"] = copy.get("hashtags", [])
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    if auto_produce:
        out["prometheus_jobs"] = _kick_prometheus(out, platforms or ["tiktok"])
    return out


def _kick_prometheus(kit, platforms):
    """Fire-and-forget POST to Prometheus /produce for each platform. Returns list of {platform, job_id|error}."""
    results = []
    kw = (kit.get("product_keyword") or "").strip()
    if not kw:
        return results
    for plat in platforms:
        try:
            req = urllib.request.Request(
                f"{PROMETHEUS_URL}/produce",
                data=json.dumps({"product_keyword": kw, "platform": plat}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                body = json.loads(r.read().decode("utf-8", errors="replace"))
            results.append({"platform": plat, "job_id": body.get("job_id"), "status": body.get("status")})
        except Exception as e:
            results.append({"platform": plat, "error": f"{type(e).__name__}: {e}"})
    return results


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "kitchen"
    print(json.dumps(generate_kit(kw, None), indent=2))