// ═══════════════════════════════════════════════════════════════
// Dropship OS — Memory Search API (Vercel Edge Function)
//
// Routes semantic search queries through Quinn bridge to Qdrant.
// Falls back to Quinn bridge LLM if Qdrant search is offline.
//
// POST /api/search
//   body: { query: string, collection?: string, top_k?: number }
//
// Vercel env vars:
//   QUINN_ENDPOINT       — ngrok URL for Quinn bridge
//   QUINN_BRIDGE_SECRET  — bridge auth token
//   QUINN_BRIDGE_URL     — fallback LLM endpoint (default http://127.0.0.1:8765)
// ═══════════════════════════════════════════════════════════════

export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: CORS });
  }
  if (req.method !== 'POST') {
    return json(405, { error: 'POST only' });
  }

  let body;
  try { body = await req.json(); } catch { return json(400, { error: 'Invalid JSON' }); }

  const { query, collection = 'dropship_intel', top_k = 5 } = body;
  if (!query) return json(400, { error: 'query is required' });

  const endpoint = process.env.QUINN_ENDPOINT;
  const secret   = process.env.QUINN_BRIDGE_SECRET;
  const quinnBridgeUrl = process.env.QUINN_BRIDGE_URL || 'http://127.0.0.1:8765';

  // ── Route 1: Quinn bridge /search ─────────────────────────────
  if (endpoint) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (secret) headers['Authorization'] = `Bearer ${secret}`;

      const res = await fetch(`${endpoint}/search`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query, collection, top_k }),
        signal: AbortSignal.timeout(10000),
      });

      if (res.ok) {
        const data = await res.json();
        return json(200, {
          results: data.results || [],
          source: 'quinn_qdrant',
          collection,
          query,
        });
      }
    } catch (e) {
      // Fall through to Claude fallback
    }
  }

  // ── Route 2: Fallback — answer via Quinn bridge LLM ──────────────
  try {
    const res = await fetch(`${quinnBridgeUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: process.env.FALLBACK_MODEL || 'qwen2.5:7b',
        max_tokens: 600,
        messages: [{
          role: 'user',
          content: `You are the ShipStack AI memory system. Answer this dropshipping question concisely using Gary Vee, Hormozi, and Kamil Sattar frameworks:

Query: ${query}

Respond as 3-5 short bullet points. Be specific and tactical.`,
        }],
      }),
      signal: AbortSignal.timeout(15000),
    });

    if (res.ok) {
      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content || data?.content?.[0]?.text || '';
      return json(200, {
        results: [{
          text,
          project: 'quinn_fallback',
          section: 'AI Response',
          score: 1.0,
          source: 'quinn_bridge',
        }],
        source: 'quinn_fallback',
        collection,
        query,
        message: 'Quinn Qdrant search offline -- answered via Quinn bridge LLM. Start Quinn bridge /search for Qdrant results.',
      });
    }
  } catch (e) {
    // Fall through
  }

  return json(503, {
    error: 'Memory search unavailable',
    message: 'Start Quinn bridge: START_QUINN_BRIDGE.bat + ngrok http 8765, then set QUINN_ENDPOINT in Vercel.',
    results: [],
  });
}

function json(status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
