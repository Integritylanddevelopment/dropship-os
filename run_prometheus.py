"""Simple launcher — runs prometheus_engine.py with correct env and args."""
import os, sys, subprocess
from pathlib import Path

BASE = Path(__file__).parent
FFMPEG = r"C:\Users\integ\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUNBUFFERED"] = "1"
env["PATH"] = env["PATH"] + ";" + FFMPEG

args = sys.argv[1:] if len(sys.argv) > 1 else [
    "--product", "Pet Lint Roller Pro",
    "--niche", "pet accessories",
    "--music", "--voiceover"
]

log = open(BASE / "prometheus_run.log", "w", encoding="utf-8")
proc = subprocess.run(
    [sys.executable, str(BASE / "prometheus_engine.py")] + args,
    env=env, cwd=str(BASE), stdout=log, stderr=log
)
log.close()
