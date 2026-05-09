// api/engine.js
// Proxies all /api/engine/* requests to the local ShipStack Engine via tunnel
// Frontend calls /api/engine/research/run → this forwards to SHIPSTACK_ENGINE_URL/api/research/run

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  const engineUrl = process.env.SHIPSTACK_ENGINE_URL;
  if (!engineUrl) {
    return res.status(503).json({
      error: 'SHIPSTACK_ENGINE_URL not configured',
      hint: 'Run LAUNCH_SHIPSTACK.ps1 to start the engine tunnel'
    });
  }

  // Extract sub-path: /api/engine/research/run -> /api/research/run
  const subPath = req.url.replace(/^\/api\/engine/, '') || '/';
  const targetUrl = `${engineUrl}/api${subPath}`;

  try {
    const fetchOptions = {
      method: req.method,
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(60000),
    };

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      fetchOptions.body = JSON.stringify(req.body || {});
    }

    const response = await fetch(targetUrl, fetchOptions);
    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (err) {
    return res.status(502).json({
      error: 'Engine unreachable',
      detail: err.message,
      target: targetUrl,
      hint: 'Make sure LAUNCH_SHIPSTACK.ps1 is running and the engine tunnel is active'
    });
  }
}
