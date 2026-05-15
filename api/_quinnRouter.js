// ============================================================
// api/_quinnRouter.js — Quinn-first LLM router
//
// Rule: Quinn is ALWAYS called first.
// Fallback to Anthropic only when Quinn is unreachable or errors.
// All config comes from environment variables via _config.js.
// ============================================================

import { env } from './_config.js';
import { logToolCall } from './_toolCallLogger.js';
import { runFallback } from './_fallbackController.js';

/**
 * Route messages through Quinn. On failure, triggers fallback.
 * @param {Array<{role: string, content: string}>} messages
 * @param {string} [context]   Optional page/domain context string
 * @returns {Promise<Object>}  {provider, model, content, fallbackTriggered, source, ...}
 */
export async function routeToQuinn(messages, context = '') {
  const quinnEndpoint = env.quinn.endpoint;

  if (!quinnEndpoint) {
    // Quinn bridge not configured — go straight to fallback
    logToolCall({
      source: 'QuinnCommandCenter',
      destination: 'quinn',
      model: env.quinn.model,
      fallbackTriggered: true,
      status: 'error',
      error: 'QUINN_ENDPOINT not set — skipping to fallback',
    });
    return runFallback(messages);
  }

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (env.quinn.secret) {
      headers['Authorization'] = `Bearer ${env.quinn.secret}`;
    }

    const response = await fetch(`${quinnEndpoint}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ messages, context }),
      signal: AbortSignal.timeout(env.quinn.timeoutMs),
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || `Quinn returned ${response.status}`);
    }

    logToolCall({
      source: 'QuinnCommandCenter',
      destination: 'quinn',
      model: env.quinn.model || data.model || 'unknown',
      fallbackTriggered: false,
      status: 'success',
    });

    return {
      provider: 'quinn',
      model: env.quinn.model || data.model || 'quinn-local',
      content: data.content || data.message || data.response || '',
      fallbackTriggered: false,
      source: data.source || 'quinn_bridge',
      context_injected: data.context_injected || false,
      qdrant_hits: data.qdrant_hits || 0,
      routed_via: 'quinn_bridge',
    };
  } catch (error) {
    logToolCall({
      source: 'QuinnCommandCenter',
      destination: 'quinn',
      model: env.quinn.model,
      fallbackTriggered: false,
      status: 'error',
      error: error.message,
    });

    console.error('[quinn-router] Quinn unreachable:', error.message, '— triggering fallback');
    return runFallback(messages);
  }
}
