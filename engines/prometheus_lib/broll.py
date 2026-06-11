"""broll.py - fetch stock video b-roll.

Tier order:
  1. Pexels videos search (PEXELS_API_KEY required)
  2. Pixabay videos search (PIXABAY_API_KEY required)
  3. Pollinations static-image Ken Burns fallback (no key, always works)

All produce mp4 files in out_dir. Returns list of absolute paths.
"""
import os, sys, urllib.parse, urllib.request, json, subprocess, shutil, random, re
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"
PEXELS_API = "https://api.pexels.com/videos/search"
PIXABAY_API = "https://pixabay.com/api/videos/"
UA = "Mozilla/5.0 (ShipStack/Prometheus)"


def _safe_name(s):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", (s or "asset"))[:48] or "asset"


def _http_get(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _download_to(url, path, timeout=60, headers=None):
    data = _http_get(url, timeout=timeout, headers=headers)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(data)
    return path


def _ffmpeg_bin():
    """Find ffmpeg.exe."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for p in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Users\integ\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
    ]:
        if os.path.exists(p):
            return p
    return None


def _try_pexels(keyword, out_dir, count, key):
    headers = {"Authorization": key, "User-Agent": UA}
    url = f"{PEXELS_API}?{urllib.parse.urlencode({'query': keyword, 'per_page': count, 'orientation': 'portrait'})}"
    try:
        data = json.loads(_http_get(url, timeout=20, headers=headers).decode("utf-8", "replace"))
    except Exception as e:
        return [], f"pexels fetch failed: {e}"
    paths = []
    for i, v in enumerate(data.get("videos", [])[:count]):
        files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0))
        target = next((f for f in files if (f.get("width") or 0) >= 720), files[-1] if files else None)
        if not target:
            continue
        out = os.path.join(out_dir, f"pexels_{_safe_name(keyword)}_{i}.mp4")
        try:
            _download_to(target["link"], out, timeout=60)
            paths.append(out)
        except Exception:
            continue
    return paths, "pexels ok" if paths else "pexels empty"


def _try_pixabay(keyword, out_dir, count, key):
    url = f"{PIXABAY_API}?{urllib.parse.urlencode({'key': key, 'q': keyword, 'per_page': max(3, count), 'video_type': 'film'})}"
    try:
        data = json.loads(_http_get(url, timeout=20).decode("utf-8", "replace"))
    except Exception as e:
        return [], f"pixabay fetch failed: {e}"
    paths = []
    for i, hit in enumerate(data.get("hits", [])[:count]):
        vids = hit.get("videos") or {}
        pick = vids.get("medium") or vids.get("small") or vids.get("tiny") or vids.get("large")
        if not pick or not pick.get("url"):
            continue
        out = os.path.join(out_dir, f"pixabay_{_safe_name(keyword)}_{i}.mp4")
        try:
            _download_to(pick["url"], out, timeout=60)
            paths.append(out)
        except Exception:
            continue
    return paths, "pixabay ok" if paths else "pixabay empty"


def _pollinations_image_url(prompt, w=1080, h=1920):
    enc = urllib.parse.quote(prompt)
    return f"{POLLINATIONS_BASE}{enc}?width={w}&height={h}&nologo=true"


def _ken_burns_clip(image_path, out_path, duration=4.0, w=1080, h=1920):
    """Animate a still image as a slow zoom+pan (Ken Burns)."""
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found for Ken Burns fallback")
    fps = 30
    frames = int(duration * fps)
    # Slow zoom-in with slight pan; resolution stays at output w/h
    vf = (
        f"scale={w*2}:{h*2},"
        f"zoompan=z='min(zoom+0.0015,1.30)':d={frames}:x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},format=yuv420p"
    )
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-i", image_path,
        "-vf", vf, "-c:v", "libx264", "-t", str(duration),
        "-pix_fmt", "yuv420p", "-preset", "veryfast", "-an",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return out_path


def _free_image_sources(keyword, w, h, seed):
    """Return ordered list of free image URLs to try."""
    kw_q = urllib.parse.quote(keyword)
    return [
        # picsum.photos: random photo, deterministic with seed
        f"https://picsum.photos/seed/{kw_q}{seed}/{w}/{h}",
        # loremflickr: keyword-matched free photo
        f"https://loremflickr.com/{w}/{h}/{kw_q}?lock={seed}",
        # source.unsplash.com (random, no key)
        f"https://source.unsplash.com/random/{w}x{h}/?{kw_q}&sig={seed}",
        # pollinations (last resort, may 402)
        _pollinations_image_url(f"{keyword} product hero vertical", w, h),
    ]


def _pollinations_fallback(keyword, out_dir, count, w=1080, h=1920):
    """Try multiple free image sources, animate each as Ken Burns clip."""
    paths = []
    for i in range(count):
        seed = random.randint(1, 99999)
        img_path = os.path.join(out_dir, f"img_{_safe_name(keyword)}_{i}.jpg")
        clip_path = os.path.join(out_dir, f"img_{_safe_name(keyword)}_{i}.mp4")
        got_img = False
        for url in _free_image_sources(keyword, w, h, seed + i * 10):
            try:
                _download_to(url, img_path, timeout=60,
                              headers={"User-Agent": UA, "Accept": "image/*"})
                if os.path.getsize(img_path) > 5000:
                    got_img = True
                    break
            except Exception as e:
                sys.stderr.write(f"[broll] image src {url[:60]} failed: {e}\n")
        if not got_img:
            sys.stderr.write(f"[broll] all image sources failed for slide {i}\n")
            continue
        try:
            _ken_burns_clip(img_path, clip_path, duration=4.0, w=w, h=h)
            paths.append(clip_path)
        except Exception as e:
            sys.stderr.write(f"[broll] ken_burns slide {i} failed: {e}\n")
    return paths


def fetch_broll(keyword, out_dir, count=3, dimensions=(1080, 1920)):
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    keyword = (keyword or "product").strip()
    w, h = dimensions

    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "").strip()
    notes = []

    if pexels_key:
        paths, note = _try_pexels(keyword, out_dir, count, pexels_key)
        notes.append(note)
        if paths:
            return paths
    else:
        notes.append("pexels skipped (no PEXELS_API_KEY)")

    if pixabay_key:
        paths, note = _try_pixabay(keyword, out_dir, count, pixabay_key)
        notes.append(note)
        if paths:
            return paths
    else:
        notes.append("pixabay skipped (no PIXABAY_API_KEY)")

    sys.stderr.write("[broll] " + " | ".join(notes) + " -> pollinations fallback\n")
    paths = _pollinations_fallback(keyword, out_dir, count, w=w, h=h)
    if not paths:
        raise RuntimeError("broll: all sources failed (pexels/pixabay/pollinations)")
    return paths


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "kitchen"
    out = sys.argv[2] if len(sys.argv) > 2 else "broll_test"
    paths = fetch_broll(kw, out, count=3)
    for p in paths:
        print(p, os.path.getsize(p))