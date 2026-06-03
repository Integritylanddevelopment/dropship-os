# Prometheus Engine — Handoff Document
**Date:** May 9, 2026  
**Project:** Drop Shipping AI Video Pipeline  
**Location:** `C:\Users\integ\Documents\Claude\Projects\Drop shipping\`

---

## What Prometheus Does
Fully automated AI dropshipping video pipeline. Give it a product name and niche, it produces 6 platform-ready video clips (TikTok, Instagram Reels, YouTube Shorts, Pinterest, Facebook, X/Twitter).

## Current Status: WORKING ✅
First successful run completed. Video generated, 6 clips exported to `prometheus_output\`.

---

## Files
| File | Purpose |
|---|---|
| `prometheus_engine.py` | Main pipeline script |
| `RUN_PROMETHEUS_NOW.bat` | Launch script (double-click or run from CMD) |
| `.env` | All API keys |
| `prometheus_run.log` | Output log from last run |
| `prometheus_output\` | Generated video clips |

## How to Run
Double-click `RUN_PROMETHEUS_NOW.bat` or:
```
cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping"
RUN_PROMETHEUS_NOW.bat
```
To change the product, edit the bat file line:
```
python prometheus_engine.py --product "YOUR PRODUCT" --niche "your niche" --music --voiceover
```

---

## API Keys (all in .env)
| Service | Status | Notes |
|---|---|---|
| `RUNWAY_API_KEY` | Working | Dev portal: dev.runwayml.com |
| `ELEVENLABS_API_KEY` | 401 Error — needs fix | api.elevenlabs.io |
| `HEYGEN_API_KEY` | Configured | Not yet used in pipeline |
| `ANTHROPIC_API_KEY` | Not configured | Optional — Ollama used instead |

---

## Runway ML Setup
- **Consumer app** (app.runwayml.com): Pro plan, $37.31/mo, 2,250 credits — for web use only
- **Developer API** (dev.runwayml.com): Separate credits at $0.01 each — what Prometheus uses
- **Model:** `gen4.5` — 12 credits/second, 10s video = 120 credits = $1.20/video
- **Ratio:** `720:1280` (portrait 9:16 for social)
- **Org ID:** `92f9c694-fa2b-4668-b8bc-56568b9a59f5`

---

## Known Issues to Fix

### 1. ElevenLabs 401 Unauthorized (HIGH PRIORITY)
Voiceover and background music both failing with HTTP 401.  
- Check `ELEVENLABS_API_KEY` in `.env` is correct and active
- Voiceover: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
- Music: `POST https://api.elevenlabs.io/v1/sound-generation`
- Fix is in `generate_voiceover()` and `generate_music()` functions

### 2. Captions Failing (MEDIUM)
Whisper caption burn failing on all 6 clips — returning original video without captions.
- Check `burn_captions()` function — likely FFmpeg subtitle filter issue
- Whisper is installed and working (shows `[OK]` in tool check)

### 3. Deprecation Warning (LOW)
`datetime.utcnow()` deprecated in Python 3.12 — replace with `datetime.now(datetime.UTC)` on line ~697

---

## Pipeline Steps (in order)
1. **Script generation** — Ollama (local LLM) writes hook/problem/solution/CTA
2. **AI video** — Runway Gen-4.5 text-to-video (10s, portrait)
3. **Voiceover** — ElevenLabs TTS (currently broken — 401)
4. **Background music** — ElevenLabs Sound Generation (currently broken — 401)
5. **Audio mix** — FFmpeg mixes voiceover + music over video
6. **Platform cuts** — FFmpeg trims/formats for each platform
7. **Captions** — Whisper transcribes + burns subtitles (currently failing)
8. **Manifest** — JSON summary saved to `prometheus_output\`

---

## What a Good Run Looks Like
```
[OK] Pipeline complete!
   Clips: 6
   TikTok     : Pet_Lint_Roller_Pro_tiktok.mp4
   Instagram  : Pet_Lint_Roller_Pro_instagram.mp4
   ...
[DONE] Exit code: 0
```

---

## Next Steps for New Chat
1. Fix ElevenLabs 401 — verify/replace API key
2. Fix caption burning
3. Test full pipeline with working audio
4. Then scale: run for multiple products automatically
