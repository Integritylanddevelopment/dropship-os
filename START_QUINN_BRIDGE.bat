@echo off
:: ═══════════════════════════════════════════════════════════════
:: Quinn Web Bridge — Start Script
:: Starts the bridge on port 8765, locked with your secret token.
:: ═══════════════════════════════════════════════════════════════

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Quinn Web Bridge — Starting                ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Set your secret token here (change this to something unique!)
:: This token must also be in Vercel: QUINN_BRIDGE_SECRET = same value
set QUINN_BRIDGE_SECRET=dropship-os-quinn-2026-alex

:: Set your Anthropic API key if not already in Windows env vars
:: (Only needed here if you haven't added it to System Environment Variables)
:: set ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE

:: Qdrant + Ollama hosts (defaults — change if running on another machine)
set QDRANT_HOST=127.0.0.1
set QDRANT_PORT=6333
set OLLAMA_HOST=127.0.0.1
set OLLAMA_PORT=11434
set QUINN_LOCAL_MODEL=qwen2.5:7b
set QUINN_COMPRESS_MODEL=qwen2.5:3b

echo  Secret token: %QUINN_BRIDGE_SECRET%
echo  Qdrant:       %QDRANT_HOST%:%QDRANT_PORT%
echo  Ollama:       %OLLAMA_HOST%:%OLLAMA_PORT%
echo.

:: Navigate to the dropship-os folder
cd /d "%~dp0"

:: Start the bridge
echo  Starting bridge on port 8765...
echo.
python quinn_web_bridge.py --port 8765

pause
