// ═══════════════════════════════════════════════════════════════
// Dropship OS — Prometheus Engine API (Vercel Edge Function)
//
// Routes pipeline requests from content.html to the local
// Prometheus Engine running on the user's machine.
//
// Flow:
//   content.html → POST /api/prometheus → Quinn bridge (ngrok)
//                → prometheus_engine.py running locally
//
// Vercel env vars required:
//   QUINN_ENDPOINT         — ngrok URL for local machine
//   QUINN_BRIDGE_SECRET    — auth token
//   QUINN_BRIDGE_URL       — Quinn bridge for script generation fallback
// ═══════════════════════════════════════════════════════════════

export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: CORS });
  }

  const url = new URL(req.url);
  const action = url.searchParams.get('action') || 'pipeline';

  // ── GET /api/prometheus?action=status ─────────────────────────
  if (req.method === 'GET' && action === 'status') {
    const localStatus = await probeLocalEngine();
    return json(200, {
      prometheus_local: localStatus,
      quinn_available: !!process.env.QUINN_ENDPOINT,
      quinn_endpoint: process.env.QUINN_ENDPOINT || null,
    });
  }

  // ── GET /api/prometheus?action=job&id=job_xxx ────────────────
  if (req.method === 'GET' && action === 'job') {
    const jobId = url.searchParams.get('id');
    if (!jobId) return json(400, { error: 'Missing job id' });
    const result = await forwardToLocal(`/jobs/${jobId}`, 'GET', null);
    if (result) return json(200, result);
    return json(503, { error: 'Prometheus Engine offline or job not found' });
  }

  // ── POST /api/prometheus — Run full pipeline ──────────────────
  if (req.method !== 'POST') {
    return json(405, { error: 'Method not allowed' });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json(400, { error: 'Invalid JSON body' });
  }

  const { product, niche, script, image_url, platforms, music, voiceover } = body;

  if (!product) {
    return json(400, { error: 'product is required' });
  }

  // ── Try local Prometheus Engine first ─────────────────────────
  const localResult = await forwardToLocal('/pipeline', 'POST', {
    product,
    niche: niche || 'general',
    script,
    image_path: null, // image_url handled differently
    platforms: platforms || ['tiktok', 'instagram', 'youtube', 'pinterest'],
    music: music || false,
    voiceover: voiceover || false,
  });

  if (localResult) {
    return json(202, {
      source: 'local_engine',
      ...localResult,
    });
  }

  // ── Fallback: generate script via Quinn bridge if engine offline ──
  const quinnBridgeUrl = process.env.QUINN_BRIDGE_URL || 'http://127.0.0.1:8765';
  const scriptText = await generateScriptViaQuinn(product, niche || 'general', quinnBridgeUrl);
  if (scriptText) {
    return json(200, {
      source: 'quinn_fallback',
      status: 'script_only',
      product,
      niche: niche || 'general',
      script: scriptText,
      message: 'Local Prometheus Engine offline. Script generated via Quinn bridge. Start prometheus_engine.py --api-mode to enable full video pipeline.',
    });
  }

  return json(503, {
    error: 'Prometheus Engine offline',
    message: 'Run: python engines/prometheus_engine.py --api-mode  (in your ShipStack folder)',
    product,
  });
}

// ── Forward request to local Prometheus Engine ────────────────
async function forwardToLocal(path, method, body) {
  const endpoint = process.env.QUINN_ENDPOINT;
  if (!endpoint) return null;

  // Prometheus engine runs on the port defined by PROMETHEUS_ENGINE_PORT env var.
  // We route through Quinn bridge which proxies to it
  const prometheusUrl = `${endpoint}/prometheus${path}`;
  const secret = process.env.QUINN_BRIDGE_SECRET;

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (secret) headers['Authorization'] = `Bearer ${secret}`;

    const fetchOptions = {
      method,
      headers,
      signal: AbortSignal.timeout(60000), // 60s for video gen
    };
    if (body) fetchOptions.body = JSON.stringify(body);

    const res = await fetch(prometheusUrl, fetchOptions);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Probe local engine availability ──────────────────────────
async function probeLocalEngine() {
  const result = await forwardToLocal('/status', 'GET', null);
  return result ? { online: true, tools: result.tools } : { online: false };
}

// ── Generate script via Quinn bridge ─────────────────────────
async function generateScriptViaQuinn(product, niche, quinnUrl) {
  try {
    const res = await fetch(`${quinnUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: process.env.FALLBACK_MODEL || 'qwen2.5:7b',
        max_tokens: 400,
        messages: [{
          role: 'user',
          content: `Write a 30-second viral TikTok script for: ${product} (${niche})
Format: HOOK (0-3s) / PROBLEM (3-10s) / SOLUTION (10-20s) / PROOF (20-27s) / CTA (27-30s)
Gary Vee style: raw, authentic, max 80 words.`
        }]
      }),
      signal: AbortSignal.timeout(15000),
    });

    if (!res.ok) return null;
    const data = await res.json();
    return data?.choices?.[0]?.message?.content || data?.content?.[0]?.text || null;
  } catch {
    return null;
  }
}

// ── Helpers ──────────────────────────────────────────────────
function json(status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
