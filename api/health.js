// dropship-os/api/health.js
// Quinn Bridge health check endpoint for Vercel
// GET /api/health -> {"status": "connected"|"disconnected"|"no_endpoint", ...}

export const config = { runtime: 'edge' };

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return json(null, 200);
  }

  const endpoint = process.env.QUINN_ENDPOINT;
  const secret   = process.env.QUINN_BRIDGE_SECRET;

  if (!endpoint) {
    return json({ status: 'no_endpoint', message: 'QUINN_ENDPOINT not set in Vercel env vars' }, 503);
  }

  try {
    const headers = {};
    if (secret) headers['Authorization'] = `Bearer ${secret}`;

    const res = await fetch(`${endpoint}/health`, {
      headers,
      signal: AbortSignal.timeout(5000),
    });

    if (res.ok) {
      let body = {};
      try { body = await res.json(); } catch {}
      return json({ status: 'connected', endpoint, bridge: body });
    }

    return json({ status: 'disconnected', endpoint, http_status: res.status }, 503);
  } catch (e) {
    return json({ status: 'disconnected', endpoint, error: e.message }, 503);
  }
}

function json(data, code = 200) {
  return new Response(JSON.stringify(data), {
    status: code,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
