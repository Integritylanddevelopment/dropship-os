// ═══════════════════════════════════════════════════════════════
// Dropship OS — Memory Search API (Vercel Edge Function)
//
// Routes semantic search queries through Quinn bridge to Qdrant.
// Falls back to Claude direct if bridge is offline.
//
// POST /api/search
//   body: { query: string, collection?: string, top_k?: number }
//
// Vercel env vars:
//   QUINN_ENDPOINT       — ngrok URL for Quinn bridge
//   QUINN_BRIDGE_SECRET  — bridge auth token
//   ANTHROPIC_API_KEY    — fallback when Quinn is offline
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
  const anthropicKey = process.env.ANTHROPIC_API_KEY;

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

  // ── Route 2: Fallback — answer from configured fallback provider ─
  const fallbackUrl = process.env.FALLBACK_API_URL;
  const fallbackModel = process.env.FALLBACK_MODEL;
  if (anthropicKey && fallbackUrl && fallbackModel) {
    try {
      const res = await fetch(fallbackUrl, {
        method: 'POST',
        headers: {
          'x-api-key': anthropicKey,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          model: fallbackModel,
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
        const text = data.content?.[0]?.text || '';
        return json(200, {
          results: [{
            text,
            project: 'claude_fallback',
            section: 'AI Response',
            score: 1.0,
            source: 'anthropic_direct',
          }],
          source: 'claude_fallback',
          collection,
          query,
          message: 'Quinn bridge offline — answered via Claude. Start Quinn bridge for Qdrant search.',
        });
      }
    } catch (e) {
      // Fall through
    }
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
