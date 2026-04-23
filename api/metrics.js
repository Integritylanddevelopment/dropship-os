// ═══════════════════════════════════════════════════════════════
// Dropship OS — Live Metrics API (Vercel Edge Function)
//
// Returns a single JSON object with ALL live dashboard data:
//   - Stripe: today's revenue, orders, avg order value
//   - Qdrant: collection counts via Quinn bridge /stats
//   - Decision engine: scores, channel rankings, product combos
//     (from static metrics.json written by decision_engine.py)
//
// Vercel env vars:
//   STRIPE_SECRET_KEY      — Stripe secret key (sk_live_... or sk_test_...)
//   QUINN_ENDPOINT         — ngrok URL for Quinn bridge
//   QUINN_BRIDGE_SECRET    — bridge auth token
// ═══════════════════════════════════════════════════════════════

export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: CORS });
  }

  const [stripe, qdrant, decisions] = await Promise.allSettled([
    fetchStripe(),
    fetchQdrantStats(),
    fetchDecisions(req),
  ]);

  const revenue  = stripe.status   === 'fulfilled' ? stripe.value   : null;
  const qdrantData = qdrant.status === 'fulfilled' ? qdrant.value   : null;
  const engine   = decisions.status === 'fulfilled' ? decisions.value : null;

  const payload = {
    generated_at: new Date().toISOString(),
    stale: !engine,
    revenue: revenue ?? { today_usd: null, total_orders: null, avg_order_value: null, currency: 'usd' },
    qdrant: qdrantData ?? { dropship_intel: null, strategy_books: null, general_knowledge: null, commandcore_memory: null, total_vectors: null },
    channels:   engine?.channels   ?? [],
    top_combos: engine?.top_combos ?? [],
    scale:      engine?.scale      ?? [],
    test:       engine?.test       ?? [],
    kill:       engine?.kill       ?? [],
    products:   engine?.products   ?? [],
    summary:    engine?.summary    ?? {},
    sources: {
      stripe:    revenue   ? 'live' : 'unavailable',
      qdrant:    qdrantData ? 'live' : 'unavailable',
      decisions: engine    ? (engine.stale ? 'stale_cache' : 'live_cache') : 'unavailable',
    },
  };

  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

// ── Stripe: today's revenue + order count ───────────────────────────────────
async function fetchStripe() {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return null;

  const now   = Math.floor(Date.now() / 1000);
  const start = now - (now % 86400); // midnight UTC

  // Fetch payment intents created today
  const res = await fetch(
    `https://api.stripe.com/v1/payment_intents?created[gte]=${start}&limit=100`,
    {
      headers: { Authorization: `Bearer ${key}` },
    }
  );
  if (!res.ok) return null;

  const data = await res.json();
  const intents = data.data ?? [];
  const succeeded = intents.filter(p => p.status === 'succeeded');
  const total = succeeded.reduce((sum, p) => sum + (p.amount_received ?? 0), 0);
  const count = succeeded.length;

  return {
    today_usd: parseFloat((total / 100).toFixed(2)),
    total_orders: count,
    avg_order_value: count > 0 ? parseFloat((total / 100 / count).toFixed(2)) : 0,
    currency: 'usd',
  };
}

// ── Qdrant stats via Quinn bridge /stats ────────────────────────────────────
async function fetchQdrantStats() {
  const endpoint = process.env.QUINN_ENDPOINT;
  const secret   = process.env.QUINN_BRIDGE_SECRET;
  if (!endpoint) return null;

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (secret) headers['Authorization'] = `Bearer ${secret}`;

    const res = await fetch(`${endpoint}/stats`, { method: 'GET', headers, signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Decision engine: read metrics.json static file ─────────────────────────
async function fetchDecisions(req) {
  try {
    const base = new URL(req.url);
    const url  = `${base.protocol}//${base.host}/metrics.json`;
    const res  = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
