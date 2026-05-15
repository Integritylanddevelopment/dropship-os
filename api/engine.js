// api/engine.js -- ShipStack Engine Intelligence Layer
// Handles all /api/engine/* routes
// Priority: local engine (SHIPSTACK_ENGINE_URL) > Quinn bridge > Anthropic fallback
// NO EMOJIS -- plain text labels only

const QUINN_ENDPOINT = process.env.QUINN_ENDPOINT || '';
const QUINN_SECRET   = process.env.QUINN_BRIDGE_SECRET || '';
const ANTHROPIC_KEY  = process.env.ANTHROPIC_API_KEY || '';
const FALLBACK_URL   = process.env.FALLBACK_API_URL || '';
const FALLBACK_MODEL = process.env.FALLBACK_MODEL || '';
const ENGINE_URL     = process.env.SHIPSTACK_ENGINE_URL || '';

// ── Intelligence: Quinn first, Anthropic fallback ─────────────────────────────
async function ask(query) {
  if (QUINN_ENDPOINT) {
    try {
      const r = await fetch(QUINN_ENDPOINT + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + QUINN_SECRET },
        body: JSON.stringify({ message: query, collection: 'dropship_intel' }),
        signal: AbortSignal.timeout(9000)
      });
      if (r.ok) {
        const d = await r.json();
        const text = d.response || d.text || d.answer || JSON.stringify(d);
        if (text && text.length > 40) return { text, source: 'quinn' };
      }
    } catch (e) { /* Quinn offline */ }
  }
  if (ANTHROPIC_KEY) {
    try {
      const r = await fetch(FALLBACK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01' },
        body: JSON.stringify({ model: FALLBACK_MODEL, max_tokens: 900,
          messages: [{ role: 'user', content: query }] }),
        signal: AbortSignal.timeout(15000)
      });
      if (r.ok) {
        const d = await r.json();
        return { text: (d.content || [])[0]?.text || '', source: 'claude' };
      }
    } catch (e) { /* Anthropic offline */ }
  }
  return { text: 'Intelligence stack offline. Start Quinn bridge or add ANTHROPIC_API_KEY.', source: 'offline' };
}

// ── Static baseline data (5 live products + 7 channels) ─────────────────────
const DEFAULT_CHANNELS = [
  { key: 'tiktok_organic',    label: 'TikTok Organic',    cpm: 0,    viral_coeff: 1.6, score: 95 },
  { key: 'pinterest_organic', label: 'Pinterest Organic',  cpm: 0.28, viral_coeff: 1.4, score: 88 },
  { key: 'youtube_shorts',    label: 'YouTube Shorts',     cpm: 0,    viral_coeff: 1.2, score: 78 },
  { key: 'reddit_organic',    label: 'Reddit Organic',     cpm: 0,    viral_coeff: 1.1, score: 65 },
  { key: 'instagram_reels',   label: 'Instagram Reels',    cpm: 0,    viral_coeff: 1.0, score: 60 },
  { key: 'x_twitter',        label: 'X / Twitter',        cpm: 0,    viral_coeff: 0.9, score: 48 },
  { key: 'meta_paid',        label: 'Meta Paid Ads',      cpm: 14.9, viral_coeff: 0.8, score: 22 }
];

const DEFAULT_COMBOS = [
  { product: 'Pet Hair Remover',  channel: 'tiktok_organic',    channel_label: 'TikTok Organic',    margin_pct: 72, cpm: 0,    score: 95, action: 'SCALE' },
  { product: 'Posture Corrector', channel: 'pinterest_organic',  channel_label: 'Pinterest Organic',  margin_pct: 68, cpm: 0.28, score: 88, action: 'SCALE' },
  { product: 'Facial Roller',     channel: 'youtube_shorts',     channel_label: 'YouTube Shorts',     margin_pct: 65, cpm: 0,    score: 78, action: 'SCALE' },
  { product: 'Resistance Bands',  channel: 'instagram_reels',    channel_label: 'Instagram Reels',    margin_pct: 60, cpm: 0,    score: 60, action: 'TEST'  },
  { product: 'AB Roller',         channel: 'reddit_organic',     channel_label: 'Reddit Organic',     margin_pct: 55, cpm: 0,    score: 45, action: 'TEST'  }
];

const DEFAULT_PRODUCTS = [
  { name: 'Pet Hair Remover',  niche: 'pet accessories', margin_pct: 72, trending: true  },
  { name: 'Posture Corrector', niche: 'health fitness',  margin_pct: 68, trending: true  },
  { name: 'Facial Roller',     niche: 'beauty skincare', margin_pct: 65, trending: false },
  { name: 'Resistance Bands',  niche: 'fitness tools',   margin_pct: 60, trending: false },
  { name: 'AB Roller',         niche: 'fitness tools',   margin_pct: 55, trending: false }
];

// ── Stage handlers ────────────────────────────────────────────────────────────
async function stageResearch() {
  const [prodRes, chanRes] = await Promise.all([
    ask('Top 5 dropshipping products with highest profit margin in 2025. For each: name, niche, estimated margin %, why it sells, best supplier (Zendrop/AutoDS). Be specific and direct.'),
    ask('Cheapest organic channels for dropshipping in 2025. Rank TikTok, Pinterest, YouTube Shorts, Reddit, Instagram by CPM and viral potential. Give specific CPM numbers and best product types for each.')
  ]);
  return {
    stage: 'research', status: 'done', source: prodRes.source,
    product_intel: prodRes.text, channel_intel: chanRes.text,
    products: DEFAULT_PRODUCTS, channels: DEFAULT_CHANNELS,
    top_combos: DEFAULT_COMBOS.slice(0, 3),
    timestamp: new Date().toISOString()
  };
}

async function stageDecision() {
  const intel = await ask(
    'Gary Vee + Hormozi + Kamil Sattar dropshipping strategy 2025: top 3 product x channel combos to max volume on right now. Give: product, channel, score 0-100, action (SCALE/TEST/KILL), one-line reason. Be direct.'
  );
  const scored = DEFAULT_COMBOS.slice().sort((a, b) => b.score - a.score);
  return {
    stage: 'decision', status: 'done', source: intel.source,
    ai_recommendation: intel.text,
    top_combos: scored.slice(0, 3),
    scale: scored.filter(c => c.action === 'SCALE'),
    test:  scored.filter(c => c.action === 'TEST'),
    kill:  scored.filter(c => c.action === 'KILL'),
    summary: { scale_count: scored.filter(c => c.action === 'SCALE').length, kill_count: 0 },
    products: DEFAULT_PRODUCTS, channels: DEFAULT_CHANNELS,
    generated_at: new Date().toISOString(), timestamp: new Date().toISOString()
  };
}

async function stageShop() {
  const intel = await ask(
    'For Pet Hair Remover, Posture Corrector, Facial Roller, Resistance Bands, AB Roller: give best TikTok/Pinterest hook + key customer pain point + strongest buy reason. 2 sentences each product.'
  );
  return { stage: 'shop', status: 'done', source: intel.source, shop_intel: intel.text, products: DEFAULT_PRODUCTS, timestamp: new Date().toISOString() };
}

async function stagePrometheus() {
  const intel = await ask(
    'Write 3 viral TikTok/Pinterest scripts for dropshipping. Each: [HOOK] 3-second scroll-stopper, [BODY] problem-solution under 20 words, [CTA] one action. Products: Pet Hair Remover, Posture Corrector, Facial Roller. Formats: POV / Before-After / Curiosity.'
  );
  return { stage: 'prometheus', status: 'done', source: intel.source, scripts: intel.text, timestamp: new Date().toISOString() };
}

async function stageRevenue(req) {
  const protocol = req.headers['x-forwarded-proto'] || 'https';
  const host = req.headers['host'] || 'dropship-os-gamma.vercel.app';
  try {
    const r = await fetch(protocol + '://' + host + '/api/metrics', { signal: AbortSignal.timeout(5000) });
    if (r.ok) { const m = await r.json(); return { stage: 'revenue', status: 'done', ...m }; }
  } catch (e) { /* offline */ }
  return {
    stage: 'revenue', status: 'offline',
    channels: DEFAULT_CHANNELS, products: DEFAULT_PRODUCTS, top_combos: DEFAULT_COMBOS,
    revenue: { today_usd: null, month_usd: null, total_orders: null },
    sources: { stripe: 'offline', qdrant: 'offline', decisions: 'static' },
    message: 'Add STRIPE_SECRET_KEY to Vercel env vars to see live revenue.'
  };
}

function stageStatus() {
  return {
    status: 'online',
    activity_log: [
      '[ENGINE] ShipStack intelligence layer online',
      '[ENGINE] Quinn bridge: ' + (QUINN_ENDPOINT ? 'connected' : 'offline - start Quinn bridge'),
      '[ENGINE] Anthropic: ' + (ANTHROPIC_KEY ? 'connected' : 'no key - add ANTHROPIC_API_KEY'),
      '[ENGINE] Local engine 8889: ' + (ENGINE_URL ? 'connected via ' + ENGINE_URL : 'offline')
    ],
    timestamp: new Date().toISOString()
  };
}

// ── Main handler ──────────────────────────────────────────────────────────────
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'OPTIONS') return res.status(204).end();

  const path = req.url.replace(/^\/api\/engine/, '') || '/';

  // Proxy to local ShipStack Engine via localtunnel if available
  if (ENGINE_URL) {
    try {
      const fetchOpts = {
        method: req.method,
        headers: { 'Content-Type': 'application/json', 'bypass-tunnel-reminder': 'true' },
        signal: AbortSignal.timeout(6000)
      };
      if (req.method !== 'GET' && req.method !== 'HEAD') fetchOpts.body = JSON.stringify(req.body || {});
      const pr = await fetch(ENGINE_URL + '/api' + path, fetchOpts);
      if (pr.ok) {
        const data = await pr.json();
        return res.status(200).json(data);
      }
    } catch (e) { /* engine offline, use intelligence fallback */ }
  }

  // Intelligence fallback -- works without local engine
  let result;
  try {
    if      (path.includes('/research/run'))           result = await stageResearch();
    else if (path.includes('/decision/run'))            result = await stageDecision();
    else if (path.includes('/shop/load'))               result = await stageShop();
    else if (path.includes('/prometheus/run'))          result = await stagePrometheus();
    else if (path.includes('/agents/queue'))            result = { stage: 'agents', status: 'queued', message: 'Run social_ai_agent/pinterest_poster.py and tiktok_poster.py to post.' };
    else if (path.includes('/revenue'))                 result = await stageRevenue(req);
    else if (path.includes('/onboard-product/status'))  result = { onboarding: { status: 'idle', jobs: {} } };
    else if (path.includes('/onboard-product'))         result = { status: 'queued', message: 'Start ShipStack Engine port 8889 for full onboarding pipeline.' };
    else if (path.includes('/status'))                  result = stageStatus();
    else result = { error: 'Unknown stage: ' + path };
  } catch (e) { result = { error: e.message, path }; }

  return res.status(200).json(result);
}
