// ============================================================
// api/_localQuinnOnlyRouter.js
//
// LOCAL QUINN ONLY — used exclusively by the embedded chat box.
//
// RULES (enforced here, not just in the UI):
//   - No fallback. Ever.
//   - No Anthropic. No OpenAI. No external providers.
//   - If local Quinn is unavailable → throw. Fail closed.
//   - fallbackTriggered is ALWAYS false in every log entry.
//   - X-Quinn-Lock: local-only header sent to bridge.
//
// Import restriction: do NOT import _fallbackController.js here.
// ============================================================

import { env } from './_config.js';
import { logToolCall } from './_toolCallLogger.js';

// Deliberately NOT imported: _fallbackController.js
// Any future dev who adds that import breaks the local-only guarantee.

/**
 * Route messages to the local Quinn bridge only.
 * Throws on failure — caller must handle the error without routing elsewhere.
 *
 * @param {Array<{role: string, content: string}>} messages
 * @param {string} [context]
 * @returns {Promise<{provider: string, model: string, content: string, fallbackTriggered: false, lockedToLocalQuinn: true}>}
 */
export async function routeToLocalQuinnOnly(messages, context = '') {
  if (!env.quinnLocal.apiUrl) {
    const err = 'QUINN_LOCAL_API_URL is not set. Local Quinn is required for embedded chat.';

    logToolCall({
      source: 'EmbeddedQuinnChatBox',
      destination: 'local-quinn',
      model: env.quinnLocal.model || 'unset',
      fallbackTriggered: false,
      status: 'error',
      error: err,
    });

    throw new Error(err);
  }

  const headers = {
    'Content-Type': 'application/json',
    'X-Quinn-Lock': 'local-only',
  };
  if (env.quinnLocal.secret) {
    headers['Authorization'] = `Bearer ${env.quinnLocal.secret}`;
  }

  let response;
  try {
    response = await fetch(`${env.quinnLocal.apiUrl}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: env.quinnLocal.model,
        messages,
        context,
        routingMode: 'LOCAL_QUINN_ONLY',
        allowFallback: false,
        allowExternalProviders: false,
      }),
      signal: AbortSignal.timeout(env.quinnLocal.timeoutMs),
    });
  } catch (fetchError) {
    logToolCall({
      source: 'EmbeddedQuinnChatBox',
      destination: 'local-quinn',
      model: env.quinnLocal.model || 'unset',
      fallbackTriggered: false,
      status: 'error',
      error: fetchError.message,
    });
    // Fail closed — no routing elsewhere.
    throw new Error(`Local Quinn unreachable: ${fetchError.message}`);
  }

  if (!response.ok) {
    const body = await response.text().catch(() => '');

    logToolCall({
      source: 'EmbeddedQuinnChatBox',
      destination: 'local-quinn',
      model: env.quinnLocal.model || 'unset',
      fallbackTriggered: false,
      status: 'error',
      error: `HTTP ${response.status}: ${body.slice(0, 200)}`,
    });

    // Fail closed — no routing elsewhere.
    throw new Error(`Local Quinn returned ${response.status}. Start the Quinn bridge locally.`);
  }

  const data = await response.json();

  logToolCall({
    source: 'EmbeddedQuinnChatBox',
    destination: 'local-quinn',
    model: env.quinnLocal.model || data.model || 'quinn-local',
    fallbackTriggered: false,
    status: 'success',
  });

  return {
    provider: 'local-quinn',
    model: env.quinnLocal.model || data.model || 'quinn-local',
    content: data.content || data.message || data.response || '',
    fallbackTriggered: false,
    lockedToLocalQuinn: true,
    source: data.source || 'local_ollama',
    context_injected: data.context_injected || false,
    qdrant_hits: data.qdrant_hits || 0,
  };
}
