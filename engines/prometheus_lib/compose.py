"""compose.py - ffmpeg-based video composition.

compose_video(voice_path, broll_paths, music_path, captions, dimensions, out_path)
  - Concatenates b-roll clips
  - Scales/crops to target dimensions
  - Overlays voiceover audio (full volume)
  - Optionally mixes background music at -18dB
  - Burns caption text per-phrase using ffmpeg drawtext
  - Outputs .mp4 with H.264 + AAC

Returns dict {path, duration_sec, dimensions, size_bytes, ffmpeg_log_tail}.
"""
import os, sys, subprocess, shutil, json, math, re, tempfile
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass


def _ffmpeg_bin():
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


def _ffprobe_bin():
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    fm = _ffmpeg_bin()
    if fm:
        cand = os.path.join(os.path.dirname(fm), "ffprobe.exe")
        if os.path.exists(cand):
            return cand
    return None


def _probe_duration(path):
    ff = _ffprobe_bin()
    if not ff:
        return None
    try:
        out = subprocess.check_output(
            [ff, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            timeout=20, stderr=subprocess.STDOUT,
        ).decode("utf-8", "replace").strip()
        return float(out) if out else None
    except Exception:
        return None


def _escape_drawtext(s):
    s = (s or "").replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\\\'")
    s = s.replace(",", r"\,").replace("[", r"\[").replace("]", r"\]")
    return s


def _split_captions(text, max_chars=42):
    """Split caption text into phrases of ~max_chars."""
    if not text:
        return []
    text = re.sub(r"\s+", " ", text.strip())
    words = text.split(" ")
    phrases, cur = [], ""
    for w in words:
        if len(cur) + 1 + len(w) > max_chars and cur:
            phrases.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip() if cur else w
    if cur:
        phrases.append(cur)
    return phrases


def _build_caption_filters(captions, duration, w, h):
    """Return drawtext filter string that pulses each caption in turn."""
    if not captions:
        return ""
    n = len(captions)
    per = max(1.4, duration / n)
    parts = []
    y_expr = f"h-(h/4)"
    for i, ph in enumerate(captions):
        start = i * per
        end = (i + 1) * per
        txt = _escape_drawtext(ph)
        parts.append(
            f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{txt}':fontcolor=white:fontsize={max(36, int(h/22))}:"
            f"borderw=3:bordercolor=black@0.85:x=(w-text_w)/2:y={y_expr}:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(parts)


def _concat_broll(broll_paths, w, h, target_dur, work_dir):
    """Concat b-roll, scale/crop to w x h, trim/loop to target_dur. Returns path."""
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    list_file = os.path.join(work_dir, "concat.txt")
    # Normalize each clip first (re-encode to consistent codec/dim)
    norm_paths = []
    for i, p in enumerate(broll_paths):
        norm = os.path.join(work_dir, f"norm_{i}.mp4")
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,fps=30,format=yuv420p"
        )
        subprocess.run(
            [ffmpeg, "-y", "-i", p, "-vf", vf, "-c:v", "libx264",
             "-preset", "veryfast", "-an", "-t", "8", norm],
            check=True, capture_output=True, timeout=180,
        )
        norm_paths.append(norm)
    with open(list_file, "w", encoding="utf-8") as f:
        for np in norm_paths:
            f.write(f"file '{np.replace(chr(92), '/')}'\n")
    concat_path = os.path.join(work_dir, "concat.mp4")
    subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c:v", "libx264", "-preset", "veryfast", "-an", concat_path],
        check=True, capture_output=True, timeout=240,
    )
    # Loop or trim to target duration
    looped = os.path.join(work_dir, "looped.mp4")
    subprocess.run(
        [ffmpeg, "-y", "-stream_loop", "-1", "-i", concat_path,
         "-t", f"{target_dur:.2f}", "-c:v", "libx264", "-preset", "veryfast",
         "-an", looped],
        check=True, capture_output=True, timeout=240,
    )
    return looped


def compose_video(voice_path, broll_paths, music_path, captions,
                  dimensions=(1080, 1920), out_path="out.mp4"):
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not installed/found - cannot compose video")
    if not voice_path or not os.path.exists(voice_path):
        raise FileNotFoundError(f"voice_path missing: {voice_path}")
    if not broll_paths:
        raise ValueError("at least one b-roll clip required")

    w, h = dimensions
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    voice_dur = _probe_duration(voice_path) or 15.0
    target_dur = max(8.0, min(60.0, voice_dur + 1.0))

    work_dir = tempfile.mkdtemp(prefix="prom_compose_")
    try:
        looped = _concat_broll(broll_paths, w, h, target_dur, work_dir)
        cap_filter = _build_caption_filters(
            captions if isinstance(captions, list) else _split_captions(str(captions or "")),
            target_dur, w, h,
        )
        # Build full ffmpeg command
        if music_path and os.path.exists(music_path):
            inputs = ["-i", looped, "-i", voice_path, "-i", music_path]
            # Mix voice (1.0) + music (-18dB ~= 0.126)
            audio_filter = (
                "[1:a]volume=1.0[v];"
                "[2:a]volume=0.126,aloop=loop=-1:size=2e9[m];"
                "[v][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
            )
        else:
            inputs = ["-i", looped, "-i", voice_path]
            audio_filter = "[1:a]volume=1.0[a]"

        filter_complex = audio_filter
        if cap_filter:
            filter_complex = f"[0:v]{cap_filter}[vout];" + audio_filter
            map_v = "[vout]"
        else:
            map_v = "0:v"

        cmd = [ffmpeg, "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", map_v, "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-t", f"{target_dur:.2f}",
            "-movflags", "+faststart",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=420)
        if result.returncode != 0:
            tail = (result.stderr or b"").decode("utf-8", "replace")[-1200:]
            raise RuntimeError(f"ffmpeg compose failed (rc={result.returncode}): ...{tail}")

        return {
            "path": out_path,
            "duration_sec": _probe_duration(out_path) or target_dur,
            "dimensions": [w, h],
            "size_bytes": os.path.getsize(out_path),
            "had_music": bool(music_path and os.path.exists(music_path)),
            "broll_count": len(broll_paths),
            "captions_count": len(captions) if isinstance(captions, list) else 0,
        }
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    print(json.dumps({"ffmpeg": _ffmpeg_bin(), "ffprobe": _ffprobe_bin()}, indent=2))