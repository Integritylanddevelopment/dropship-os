"""prometheus_lib - Prometheus media generation modules.

Sub-modules:
  voice    : edge-tts voiceover generation (free, no API key)
  broll    : stock video b-roll (Pexels -> Pixabay -> Pollinations fallback)
  music    : background music selection from local library
  compose  : ffmpeg-based video composition
  pipeline : high-level produce_video(media_kit, platform) orchestrator

All modules write only under engines/prometheus_output/ and use only free tier.
"""
__version__ = "1.0.0"