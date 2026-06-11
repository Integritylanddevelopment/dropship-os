"""pipeline.py - high-level produce_video orchestrator.

produce_video(media_kit, platform, output_root=None, collateral_paths=None) -> dict
  Per-platform dimensions:
    tiktok / instagram_reels / youtube_shorts : 1080x1920 (9:16)
    pinterest                                 : 1000x1500 (2:3)

  collateral_paths: optional list of local image/video files to use INSTEAD of stock b-roll.
    Images are converted to Ken Burns clips. Videos are used as-is.
"""
import os, sys, time, re, json, traceback, subprocess
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

from . import voice as voice_mod
from . import broll as broll_mod
from . import music as music_mod
from . import compose as compose_mod

DIMENSIONS = {
    "tiktok": (1080, 1920),
    "instagram_reels": (1080, 1920),
    "youtube_shorts": (1080, 1920),
    "pinterest": (1000, 1500),
}

DEFAULT_DIMENSIONS = (1080, 1920)

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VID_EXTS = {".mp4", ".webm", ".mov", ".m4v", ".mkv"}


def _slug(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "product")).strip("_").lower()
    return s[:48] or "product"


def _voiceover_text(kit):
    hook = (kit.get("hook") or "").strip()
    caption = (kit.get("caption") or "").strip()
    kw = (kit.get("product_keyword") or "this product").strip()
    if hook and caption:
        return f"{hook}. {caption}"
    if hook:
        return hook
    if caption:
        return caption
    return f"Discover the {kw}. The trending pick everyone is talking about."


def _caption_phrases(kit):
    hook = (kit.get("hook") or "").strip()
    caption = (kit.get("caption") or "").strip()
    if hook or caption:
        text = (hook + ". " + caption).strip(". ")
        from .compose import _split_captions
        return _split_captions(text, max_chars=38)
    kw = (kit.get("product_keyword") or "product").strip()
    return [kw.upper(), "TRENDING NOW", "TAP TO SEE MORE"]


def _prepare_collateral_clips(collateral_paths, out_dir, w, h, count=4):
    """Convert mixed image/video collateral into broll-compatible mp4 clips.
    Images -> Ken Burns. Videos -> kept as-is. Returns list of paths (max `count`)."""
    if not collateral_paths:
        return []
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    clips = []
    # Prefer videos first (more natural), then images
    videos = [p for p in collateral_paths
              if os.path.exists(p) and os.path.splitext(p)[1].lower() in VID_EXTS]
    images = [p for p in collateral_paths
              if os.path.exists(p) and os.path.splitext(p)[1].lower() in IMG_EXTS]
    # Interleave: 1 video, 2 images, etc, to keep variety
    pool = []
    vi = ii = 0
    while vi < len(videos) or ii < len(images):
        if vi < len(videos):
            pool.append(videos[vi]); vi += 1
        if ii < len(images):
            pool.append(images[ii]); ii += 1
    for i, src in enumerate(pool[:count]):
        ext = os.path.splitext(src)[1].lower()
        if ext in VID_EXTS:
            clips.append(src)
        elif ext in IMG_EXTS:
            out_path = os.path.join(out_dir, f"collateral_{i}.mp4")
            try:
                broll_mod._ken_burns_clip(src, out_path, duration=4.0, w=w, h=h)
                clips.append(out_path)
            except Exception as e:
                sys.stderr.write(f"[pipeline] ken_burns failed for {src}: {e}\n")
    return clips


def produce_video(media_kit, platform, output_root=None, collateral_paths=None):
    """End-to-end produce. Returns dict with status + all asset paths."""
    if not isinstance(media_kit, dict):
        raise TypeError("media_kit must be dict")
    platform = (platform or "tiktok").strip().lower()
    dims = DIMENSIONS.get(platform, DEFAULT_DIMENSIONS)

    kw = (media_kit.get("product_keyword") or "product").strip()
    slug = _slug(kw)

    if output_root is None:
        output_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prometheus_output",
        )
    out_dir = os.path.join(output_root, slug)
    work_dir = os.path.join(out_dir, "work")
    os.makedirs(work_dir, exist_ok=True)

    t0 = time.time()
    timings = {}

    vo_text = _voiceover_text(media_kit)
    voice_path = os.path.join(work_dir, f"voice_{platform}.mp3")
    t = time.time()
    voice_mod.generate_voiceover(vo_text, voice_path)
    timings["voice_sec"] = round(time.time() - t, 2)

    t = time.time()
    used_collateral = False
    broll_paths = []
    if collateral_paths:
        broll_paths = _prepare_collateral_clips(
            collateral_paths, os.path.join(work_dir, "collateral_broll"),
            w=dims[0], h=dims[1], count=4,
        )
        if broll_paths:
            used_collateral = True
    if not broll_paths:
        broll_paths = broll_mod.fetch_broll(
            kw, os.path.join(work_dir, "broll"), count=3, dimensions=dims,
        )
    timings["broll_sec"] = round(time.time() - t, 2)

    t = time.time()
    music_path = music_mod.pick_music(duration_sec=20.0)
    timings["music_sec"] = round(time.time() - t, 2)

    captions = _caption_phrases(media_kit)
    out_path = os.path.join(out_dir, f"{platform}.mp4")
    t = time.time()
    result = compose_mod.compose_video(
        voice_path=voice_path,
        broll_paths=broll_paths,
        music_path=music_path,
        captions=captions,
        dimensions=dims,
        out_path=out_path,
    )
    timings["compose_sec"] = round(time.time() - t, 2)
    timings["total_sec"] = round(time.time() - t0, 2)

    return {
        "ok": True,
        "platform": platform,
        "product_keyword": kw,
        "slug": slug,
        "video_path": result["path"],
        "duration_sec": result["duration_sec"],
        "dimensions": result["dimensions"],
        "size_bytes": result["size_bytes"],
        "had_music": result["had_music"],
        "broll_count": result["broll_count"],
        "used_collateral": used_collateral,
        "collateral_count": len(collateral_paths) if collateral_paths else 0,
        "voiceover_text": vo_text,
        "captions": captions,
        "voice_path": voice_path,
        "broll_paths": broll_paths,
        "timings": timings,
    }


if __name__ == "__main__":
    kit = {"product_keyword": sys.argv[1] if len(sys.argv) > 1 else "kitchen",
           "hook": "This kitchen tool will change your life",
           "caption": "Cuts prep time in half and fits in a drawer.",
           "hashtags": ["#kitchen", "#cooking"]}
    plat = sys.argv[2] if len(sys.argv) > 2 else "tiktok"
    res = produce_video(kit, plat)
    print(json.dumps(res, indent=2, default=str))
