// ═══════════════════════════════════════════════════════════════
// Dropship OS — Chat API (Vercel Edge Function)
//
// Pipeline:
//   1. If QUINN_ENDPOINT is set → route through Quinn Web Bridge
//      (Qdrant search → Ollama local → Anthropic if needed)
//   2. Fallback: direct Anthropic (for cold start before bridge is up)
//
// Vercel env vars needed:
//   QUINN_ENDPOINT       = https://your-ngrok-url.ngrok.io   ← Quinn bridge URL
//   QUINN_BRIDGE_SECRET  = your-secret-token                 ← bridge auth token
//   ANTHROPIC_API_KEY    = sk-ant-...                        ← fallback + bridge uses this
// ═══════════════════════════════════════════════════════════════

export const config = { runtime: 'edge' };

const DROPSHIP_SYSTEM = `You are the Dropship OS AI — Alex Alexander's personal drop shipping intelligence agent.

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

Be direct, tactical, specific. No fluff. Actionable next steps only.`;

export default async function handler(req) {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 200,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    });
  }

  if (req.method !== 'POST') {
    return json({ error: 'POST only' }, 405);
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const { messages = [], message = '', context = '' } = body;

  // Support both {message: "..."} (single string) and {messages: [...]} (array)
  const effectiveMessages = messages.length > 0
    ? messages
    : (message ? [{ role: 'user', content: message }] : []);

  const quinnEndpoint = process.env.QUINN_ENDPOINT;
  const quinnSecret   = process.env.QUINN_BRIDGE_SECRET;
  const anthropicKey  = process.env.ANTHROPIC_API_KEY;

  // ── Route 1: Through Quinn Web Bridge ────────────────────────────────────
  if (quinnEndpoint) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (quinnSecret) {
        headers['Authorization'] = `Bearer ${quinnSecret}`;
      }

      const quinnRes = await fetch(`${quinnEndpoint}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ messages: effectiveMessages, context }),
      });

      const data = await quinnRes.json();

      if (!quinnRes.ok || data.error) {
        // Quinn bridge error — fall through to Anthropic direct
        console.error('Quinn bridge error:', data.error);
      } else {
        // Quinn succeeded — pass through its response + metadata
        return json({
          content: data.content,
          source: data.source,           // "local_ollama" or "anthropic"
          context_injected: data.context_injected,
          qdrant_hits: data.qdrant_hits,
          routed_via: 'quinn_bridge',
        });
      }
    } catch (e) {
      console.error('Quinn bridge unreachable:', e.message);
      // Fall through to direct Anthropic
    }
  }

  // ── Route 2: Direct Anthropic (fallback) ─────────────────────────────────
  if (!anthropicKey) {
    return json({
      error: 'Chat not configured. Set QUINN_ENDPOINT + QUINN_BRIDGE_SECRET in Vercel env vars to route through Quinn, or set ANTHROPIC_API_KEY for direct mode.',
      source: 'error',
    }, 500);
  }

  try {
    const system = context
      ? `${DROPSHIP_SYSTEM}\n\nCurrent page: ${context}`
      : DROPSHIP_SYSTEM;

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': anthropicKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-6',
        max_tokens: 1024,
        system,
        messages: effectiveMessages.slice(-10),
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      return json({ error: `Anthropic error ${res.status}: ${err}`, source: 'error' }, 500);
    }

    const data = await res.json();
    const content = data.content?.[0]?.text || '';

    return json({
      content,
      source: 'anthropic_direct',
      context_injected: false,
      routed_via: 'direct',
    });
  } catch (e) {
    return json({ error: `Anthropic unreachable: ${e.message}`, source: 'error' }, 500);
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
