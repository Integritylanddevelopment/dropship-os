"""music.py - pick background music from local library.

Reads MUSIC_LIBRARY_DIR env var. If unset or empty, returns None (silence).
No paid music API. No downloads. User-provided royalty-free files only.
"""
import os, sys, random
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

EXTS = (".mp3", ".m4a", ".wav", ".ogg", ".aac")


def pick_music(duration_sec=15.0):
    """Return path to a random music file at least duration_sec long, or None."""
    libdir = os.environ.get("MUSIC_LIBRARY_DIR", "").strip()
    if not libdir or not os.path.isdir(libdir):
        return None
    candidates = []
    for root, _, files in os.walk(libdir):
        for f in files:
            if f.lower().endswith(EXTS):
                candidates.append(os.path.join(root, f))
    if not candidates:
        return None
    # Simple length filter: skip files smaller than ~200KB which probably
    # can't fit duration_sec at sane bitrates. (Avoids ffprobe dependency
    # for the picker.)
    min_bytes = max(50_000, int(duration_sec) * 12_000)
    sized = [c for c in candidates if os.path.getsize(c) >= min_bytes]
    pool = sized or candidates
    return random.choice(pool)


if __name__ == "__main__":
    print(pick_music(20.0) or "(no music library; silence will be used)")