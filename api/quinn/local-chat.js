// ============================================================
// api/quinn/local-chat.js — Local Quinn Only chat endpoint
// (Vercel Edge Function)
//
// Used exclusively by the embedded Quinn chat box.
//
// CONTRACT:
//   - Routes to local Quinn bridge only (QUINN_LOCAL_API_URL).
//   - If Quinn is unavailable → 503. Fail closed.
//   - NO fallback. NO Anthropic. NO OpenAI. NO external providers.
//   - X-Quinn-Lock: local-only is enforced here AND forwarded to bridge.
//
// Validation commands:
//   grep -R "fallbackController\|anthropic\|openai\|FALLBACK" api/quinn/
//   (must return zero matches)
// ============================================================

import { routeToLocalQuinnOnly } from '../_localQuinnOnlyRouter.js';

export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-Quinn-Lock',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: CORS });
  }

  if (req.method !== 'POST') {
    return json({ error: 'POST only' }, 405);
  }

  // Enforce local-only lock from client side too
  const lockHeader = req.headers.get('X-Quinn-Lock');
  if (lockHeader && lockHeader !== 'local-only') {
    return json({ error: 'Invalid routing lock. This endpoint is local Quinn only.' }, 403);
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const { messages = [], context = '' } = body;

  if (!Array.isArray(messages) || messages.length === 0) {
    return json({ error: 'messages must be a non-empty array' }, 400);
  }

  try {
    const result = await routeToLocalQuinnOnly(messages, context);
    return json(result, 200);
  } catch (error) {
    // Fail closed — 503, no fallback, no redirect.
    return json({
      error: error.message,
      lockedToLocalQuinn: true,
      fallbackUsed: false,
      hint: 'Start the Quinn bridge locally: START_QUINN_BRIDGE.bat',
    }, 503);
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json' },
  });
}
