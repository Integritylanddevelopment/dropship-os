#!/usr/bin/env python3
"""
Quinn Web Bridge — HTTP gateway to the Quinn local pipeline.

Exposes Quinn's full pipeline over HTTP so Vercel-hosted pages can reach it:
  POST /chat  →  Qdrant search → Ollama local → Anthropic (if needed)

Architecture:
  Vercel page → /api/chat.js (Vercel Edge) → QUINN_ENDPOINT (ngrok URL)
                → This bridge → Qdrant semantic search (general_knowledge)
                             → Ollama (qwen2.5:7b) with context injected
                             → If not confident → compress → Anthropic
                             → Return {content, source, context_injected}

SETUP:
  1. Install deps:  pip install httpx sentence-transformers qdrant-client
  2. Run bridge:    python quinn_web_bridge.py
  3. Expose ngrok:  ngrok http 8765
  4. Set in Vercel: QUINN_ENDPOINT = https://your-ngrok-url.ngrok.io
  5. Redeploy Vercel — chat now routes through Quinn
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional

import httpx

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [quinn-bridge] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("quinn-bridge")

# ── Config ────────────────────────────────────────────────────────────────────

QDRANT_HOST    = os.environ.get("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT    = int(os.environ.get("QDRANT_PORT", "6333"))
OLLAMA_HOST    = os.environ.get("OLLAMA_HOST", "127.0.0.1")
OLLAMA_PORT    = int(os.environ.get("OLLAMA_PORT", "11434"))
OLLAMA_MODEL   = os.environ.get("QUINN_LOCAL_MODEL", "qwen2.5:7b")
COMPRESS_MODEL = os.environ.get("QUINN_COMPRESS_MODEL", "qwen2.5:3b")

ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_KEY     = os.environ.get("OPENAI_API_KEY", "")
BRIDGE_SECRET  = os.environ.get("QUINN_BRIDGE_SECRET", "")

# Partitioned collections — run SETUP_QDRANT_PARTITIONS.py first to create these.
# Falls back to general_knowledge if dropship_intel doesn't exist yet.
QDRANT_COLLECTIONS = ["dropship_intel", "general_knowledge"]
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

DROPSHIP_SYSTEM = """You are the Dropship OS AI — Alex Alexander's personal drop shipping intelligence agent.

Core knowledge:
- Gary Vee: find cheapest attention channels (Pinterest, TikTok, YouTube Shorts) before saturation
- Hormozi: stack value so high saying no feels stupid; guarantee-backed offers
- Kamil Sattar (Ecom King): AI-powered execution — move fast with automation
- Products: high-margin $40-200, trending, low competition niches
- Channel strategy: highest-margin product × cheapest-attention channel
- Pinterest: pins compound 2-4 years, saves = algorithm signal, buyer intent is high
- TikTok: 2-second hooks, trending sounds, problem-solution format
- Content: 1 pillar piece → 10+ micro pieces across all channels
- Suppliers: Zendrop, AutoDS, AliExpress, CJ Dropshipping
- Tech stack: GitHub Pages / Vercel landing pages + Stripe payment links

Alex's system: real-time attention tracking → product-channel matching → auto content → auto fulfillment.

Be direct, tactical, specific. No fluff. Actionable next steps only."""

# ── Embedding ─────────────────────────────────────────────────────────────────

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedder ready (all-MiniLM-L6-v2)")
        except Exception as e:
            logger.warning(f"No embedder: {e} — Qdrant search disabled")
    return _embedder

def embed_text(text: str) -> Optional[list]:
    emb = get_embedder()
    if emb is None:
        return None
    try:
        return emb.encode(text[:512]).tolist()
    except Exception:
        return None

# ── Qdrant search ─────────────────────────────────────────────────────────────

async def search_qdrant(query: str, top_k: int = 5) -> list:
    """Search Qdrant for relevant context from all research sessions."""
    vector = embed_text(query)
    if vector is None:
        return []

    results = []
    async with httpx.AsyncClient() as client:
        for collection in QDRANT_COLLECTIONS:
            try:
                resp = await client.post(
                    f"{QDRANT_URL}/collections/{collection}/points/search",
                    json={"vector": vector, "limit": top_k, "with_payload": True, "score_threshold": 0.4},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    for h in resp.json().get("result", []):
                        payload = h.get("payload", {})
                        text = payload.get("text", "") or payload.get("content", "") or str(payload)
                        if text:
                            results.append({
                                "text": text[:800],
                                "score": h.get("score", 0),
                                "source": collection,
                                "section": payload.get("section", ""),
                                "project": payload.get("project", ""),
                            })
            except Exception as e:
                logger.debug(f"Qdrant {collection}: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def build_context_block(results: list, max_chars: int = 2000) -> str:
    if not results:
        return ""
    parts = ["### Quinn Memory (relevant research):"]
    total = 0
    for r in results:
        label = r.get("project") or r.get("source") or "memory"
        chunk = f"\n[{label} | {r['score']:.2f}]\n{r['text']}"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)

# ── Ollama local ──────────────────────────────────────────────────────────────

UNCERTAINTY = [
    "i don't know", "i'm not sure", "i cannot", "i can't",
    "i don't have", "beyond my", "i lack", "not enough information",
    "unable to", "outside my", "i'm unable", "don't have access",
    "cannot determine", "insufficient", "i need to escalate",
]

async def try_ollama(message: str, context_block: str) -> Optional[str]:
    system = DROPSHIP_SYSTEM
    if context_block:
        system += f"\n\n{context_block}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": message},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1024},
                },
                timeout=25.0,
            )
            resp.raise_for_status()
            text = resp.json().get("message", {}).get("content", "").strip()
            if not text or len(text) < 30:
                return None
            if any(s in text.lower() for s in UNCERTAINTY):
                logger.info("Ollama uncertain — escalating")
                return None
            logger.info(f"Ollama local response ({len(text)} chars)")
            return text
    except Exception as e:
        logger.debug(f"Ollama skipped: {e}")
        return None

async def compress_message(message: str) -> str:
    if len(message) < 300:
        return message
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": COMPRESS_MODEL,
                    "messages": [
                        {"role": "system", "content": "Rewrite this message concisely. Keep all key info — names, numbers, code, the core question. Remove filler. Output ONLY the rewritten message."},
                        {"role": "user", "content": message},
                    ],
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 512},
                },
                timeout=12.0,
            )
            resp.raise_for_status()
            compressed = resp.json().get("message", {}).get("content", "").strip()
            if compressed and len(compressed) < len(message):
                pct = round((1 - len(compressed) / len(message)) * 100)
                logger.info(f"Compressed {len(message)}→{len(compressed)} chars ({pct}% saved)")
                return compressed
    except Exception:
        pass
    return message

# ── Anthropic cloud ───────────────────────────────────────────────────────────

async def call_anthropic(message: str, context_block: str, history: list) -> str:
    system = DROPSHIP_SYSTEM
    if context_block:
        system += f"\n\n{context_block}"

    messages = []
    for m in history[-8:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    # Ensure last message is from user
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": message})
    elif messages[-1]["content"] != message:
        messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "system": system,
                "messages": messages,
            },
            timeout=45.0,
        )
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return " ".join(p.get("text","") for p in parts if isinstance(p,dict) and p.get("type")=="text").strip()

# ── Main pipeline ─────────────────────────────────────────────────────────────

COMPLEX_TRIGGERS = ["write a", "create a", "draft", "analyze", "explain in detail", "compare and contrast", "help me write", "build a", "implement"]

async def handle_chat(message: str, history: list, page_context: str = "") -> dict:
    """
    Quinn pipeline:
    1. Qdrant semantic search (general_knowledge + commandcore_memory)
    2. Build context block from top results
    3. Try Ollama local with context injected
    4. If not confident → compress locally → call Anthropic with context
    """
    query = f"{page_context} {message}".strip() if page_context else message

    # 1. Qdrant search
    qdrant_results = await search_qdrant(query, top_k=5)
    context_block = build_context_block(qdrant_results)
    best_score = qdrant_results[0]["score"] if qdrant_results else 0.0
    logger.info(f"Qdrant: {len(qdrant_results)} hits, best={best_score:.2f}")

    # 2. Try Ollama (only if good context AND not complex task)
    is_complex = any(t in message.lower() for t in COMPLEX_TRIGGERS)
    local_text = None
    if best_score > 0.55 and not is_complex:
        local_text = await try_ollama(message, context_block)

    if local_text:
        return {
            "content": local_text,
            "source": "local_ollama",
            "context_injected": bool(context_block),
            "qdrant_hits": len(qdrant_results),
        }

    # 3. Escalate to Anthropic
    if not ANTHROPIC_KEY:
        return {
            "error": "ANTHROPIC_API_KEY not set. Set it as a Windows environment variable and restart the bridge.",
            "source": "error",
        }

    compressed = await compress_message(message)
    try:
        text = await call_anthropic(compressed, context_block, history)
        return {
            "content": text,
            "source": "anthropic",
            "context_injected": bool(context_block),
            "compressed": compressed != message,
            "qdrant_hits": len(qdrant_results),
        }
    except Exception as e:
        return {"error": f"Anthropic error: {e}", "source": "error"}

# ── Qdrant stats (for /stats endpoint) ───────────────────────────────────────

TRACKED_COLLECTIONS = [
    "dropship_intel",
    "strategy_books",
    "general_knowledge",
    "commandcore_memory",
]

async def fetch_qdrant_stats() -> dict:
    """Return vector counts for all tracked Qdrant collections."""
    result = {c: 0 for c in TRACKED_COLLECTIONS}
    result["total_vectors"] = 0

    async with httpx.AsyncClient() as client:
        for collection in TRACKED_COLLECTIONS:
            try:
                resp = await client.get(
                    f"{QDRANT_URL}/collections/{collection}",
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    count = resp.json().get("result", {}).get("vectors_count", 0)
                    result[collection] = count
                    result["total_vectors"] += count
            except Exception as e:
                logger.debug(f"Stats {collection}: {e}")

    result["ts"] = datetime.now(timezone.utc).isoformat()
    return result

# ── HTTP handler ──────────────────────────────────────────────────────────────

class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info(f"{args[1]} {args[0]}")

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._json({
                "status": "ok",
                "bridge": "quinn-web-bridge",
                "qdrant": QDRANT_URL,
                "ollama": OLLAMA_URL,
                "anthropic_key": "set" if ANTHROPIC_KEY else "MISSING",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        elif self.path == "/stats":
            # Live Qdrant collection counts — called by /api/metrics.js
            try:
                loop = asyncio.new_event_loop()
                stats = loop.run_until_complete(fetch_qdrant_stats())
                loop.close()
                self._json(stats)
            except Exception as e:
                self._json({"error": str(e)}, 500)
        elif self.path.startswith("/prometheus/"):
            # Proxy to local Prometheus Engine (port 8766)
            self._proxy_prometheus(self.path[len("/prometheus"):], "GET", None)
        elif self.path == "/prometheus/status":
            self._proxy_prometheus("/status", "GET", None)
        else:
            self._json({"error": "Not found"}, 404)

    def _proxy_prometheus(self, subpath: str, method: str, body: bytes):
        """Forward request to local Prometheus Engine on port 8766."""
        import urllib.request
        import urllib.error
        PROMETHEUS_PORT = int(os.environ.get("PROMETHEUS_PORT", "8766"))
        url = f"http://127.0.0.1:{PROMETHEUS_PORT}{subpath}"
        try:
            req = urllib.request.Request(url, data=body, method=method)
            if body:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=120) as r:
                resp_data = r.read()
                self._json(json.loads(resp_data))
        except urllib.error.URLError as e:
            self._json({
                "error": "Prometheus Engine offline",
                "message": "Run: python prometheus_engine.py --api-mode",
                "detail": str(e)
            }, 503)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        if self.path.startswith("/prometheus/"):
            # Prometheus proxy — auth check first
            if BRIDGE_SECRET:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {BRIDGE_SECRET}":
                    self._json({"error": "Unauthorized"}, 401)
                    return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None
            self._proxy_prometheus(self.path[len("/prometheus"):], "POST", body)
            return

        if self.path != "/chat":
            self._json({"error": "POST to /chat"}, 404)
            return

        if BRIDGE_SECRET:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {BRIDGE_SECRET}":
                self._json({"error": "Unauthorized"}, 401)
                return

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
        except Exception:
            self._json({"error": "Invalid JSON"}, 400)
            return

        # Support both {message:str} and {messages:[{role,content}]} formats
        message = data.get("message", "").strip()
        messages_arr = data.get("messages", [])
        if not message and messages_arr:
            for m in reversed(messages_arr):
                if m.get("role") == "user":
                    message = m.get("content", "").strip()
                    break

        if not message:
            self._json({"error": "No message"}, 400)
            return

        page_context = data.get("context", "")
        history = messages_arr

        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(handle_chat(message, history, page_context))
            loop.close()
            self._json(result)
        except Exception as e:
            logger.error(traceback.format_exc())
            self._json({"error": str(e)}, 500)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    Thread(target=get_embedder, daemon=True).start()

    server = HTTPServer((args.host, args.port), BridgeHandler)
    logger.info("=" * 58)
    logger.info("  Quinn Web Bridge")
    logger.info(f"  http://localhost:{args.port}/health")
    logger.info(f"  POST http://localhost:{args.port}/chat")
    logger.info(f"  Qdrant:    {QDRANT_URL}")
    logger.info(f"  Ollama:    {OLLAMA_URL} [{OLLAMA_MODEL}]")
    logger.info(f"  Anthropic: {'SET' if ANTHROPIC_KEY else 'MISSING'}")
    logger.info("=" * 58)
    logger.info("  Run ngrok: ngrok http 8765")
    logger.info("  Then in Vercel → Env Vars: QUINN_ENDPOINT=<ngrok url>")
    logger.info("=" * 58)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == "__main__":
    main()
