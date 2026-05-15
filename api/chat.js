// ============================================================
// api/chat.js — Chat API (Vercel Edge Function)
//
// Pipeline: Quinn first → fallback only on failure.
//
// All config from environment variables. See .env.example.
// Required Vercel env vars:
//   QUINN_ENDPOINT        = https://your-ngrok-url.ngrok.io
//   QUINN_BRIDGE_SECRET   = your-secret-token
//   ANTHROPIC_API_KEY     = sk-ant-...  (fallback)
//   FALLBACK_ENABLED      = true
//   FALLBACK_API_URL      = https://api.anthropic.com/v1/messages
//   FALLBACK_MODEL        = claude-sonnet-4-5
//   APP_PRIMARY_PROFILE   = quinn
// ============================================================

import { routeToQuinn } from './_quinnRouter.js';

export const config = { runtime: 'edge' };

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

  if (effectiveMessages.length === 0) {
    return json({ error: 'No messages provided' }, 400);
  }

  try {
    // Quinn is always called first. Fallback triggers automatically on failure.
    const result = await routeToQuinn(effectiveMessages, context);
    return json(result);
  } catch (e) {
    return json({ error: e.message, source: 'error' }, 500);
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
