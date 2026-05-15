// ============================================================
// api/_config.js — Shared environment config for all Edge Functions
//
// ALL runtime values come from environment variables.
// Never hard-code URLs, ports, model names, API keys, or secrets here.
// Set variables in:
//   - Local:  .env (project root, not committed)
//   - Vercel: dashboard > Settings > Environment Variables
// ============================================================

export const env = {
  // Local Quinn — embedded chat box uses THIS block ONLY.
  // No fallback. Fails closed if unavailable.
  quinnLocal: {
    apiUrl:    process.env.QUINN_LOCAL_API_URL || '',   // local bridge URL, e.g. http://localhost:8765
    model:     process.env.QUINN_LOCAL_MODEL || '',     // e.g. qwen2.5:7b
    secret:    process.env.QUINN_BRIDGE_SECRET || '',
    timeoutMs: Number(process.env.QUINN_LOCAL_TIMEOUT_MS || 30000),
  },

  quinn: {
    endpoint:    process.env.QUINN_ENDPOINT || '',          // ngrok URL to Quinn bridge
    secret:      process.env.QUINN_BRIDGE_SECRET || '',     // bearer auth token
    model:       process.env.QUINN_LOCAL_MODEL || '',       // e.g. qwen2.5:7b
    timeoutMs:   Number(process.env.QUINN_TIMEOUT_MS || 30000),
  },

  shipstack: {
    model:       process.env.SHIPSTACK_MODEL || '',
    port:        process.env.SHIPSTACK_ENGINE_PORT || '',
  },

  fallback: {
    enabled:     process.env.FALLBACK_ENABLED === 'true',
    provider:    process.env.FALLBACK_PROVIDER || 'anthropic',
    apiUrl:      process.env.FALLBACK_API_URL || '',
    model:       process.env.FALLBACK_MODEL || '',
    timeoutMs:   Number(process.env.FALLBACK_TIMEOUT_MS || 60000),
    apiKey:      process.env.ANTHROPIC_API_KEY || '',
  },

  app: {
    primaryProfile:   process.env.APP_PRIMARY_PROFILE || 'quinn',
    secondaryProfile: process.env.APP_SECONDARY_PROFILE || 'shipstack',
    siteUrl:          process.env.VERCEL_SITE_URL || '',
  },

  logging: {
    toolLogPath: process.env.TOOL_LOG_PATH || './logs/tool-calls.jsonl',
  },
};

// Validates that required variables are present at function startup.
// Call from any Edge Function that needs these values.
export function validateEnv(required = []) {
  const defaults = [
    'QUINN_BRIDGE_SECRET',
    'APP_PRIMARY_PROFILE',
  ];
  const keys = [...new Set([...defaults, ...required])];
  const missing = keys.filter((k) => !process.env[k]);
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
}

export const systemProfiles = {
  quinn: {
    name: 'Quinn',
    role: 'primary_llm_router',
    apiUrl: env.quinn.endpoint,
    model: env.quinn.model,
    directive:
      'All requests route to Quinn first. No direct external provider calls unless Quinn fails or escalates.',
  },
  shipstack: {
    name: 'ShipStack',
    role: 'marketing_ops_profile',
    model: env.shipstack.model,
    directive:
      'ShipStack is available as a secondary profile but does not bypass Quinn routing.',
  },
};
