"""voice.py - edge-tts voiceover. Free, no API key."""
import sys, asyncio, os
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import edge_tts

DEFAULT_VOICE = "en-US-AvaNeural"


async def _gen_async(text, out_path, voice=DEFAULT_VOICE, rate="+0%"):
    comm = edge_tts.Communicate(text, voice, rate=rate)
    await comm.save(out_path)


def generate_voiceover(text, out_path, voice=DEFAULT_VOICE, rate="+0%"):
    """Generate an MP3 voiceover. Returns out_path on success."""
    if not text or not text.strip():
        raise ValueError("voiceover text is empty")
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    asyncio.run(_gen_async(text, out_path, voice=voice, rate=rate))
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 200):
        raise RuntimeError(f"edge-tts produced no/small file at {out_path}")
    return out_path


def available_voices_sample():
    """Hard-coded list of commonly used English voices (avoid network at import)."""
    return [
        "en-US-AvaNeural", "en-US-AndrewNeural", "en-US-EmmaNeural",
        "en-US-GuyNeural", "en-US-JennyNeural", "en-GB-SoniaNeural",
        "en-AU-NatashaNeural",
    ]


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "voice_test.mp3"
    txt = sys.argv[2] if len(sys.argv) > 2 else "This is a Prometheus voiceover smoke test."
    out = generate_voiceover(txt, p)
    print("wrote", out, os.path.getsize(out), "bytes")