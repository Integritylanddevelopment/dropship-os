// ============================================================
// api/_fallbackController.js — Anthropic fallback (Quinn-failed path)
//
// Only called when Quinn bridge is unreachable or returns an error.
// All config comes from environment variables via _config.js.
// ============================================================

import { env } from './_config.js';
import { logToolCall } from './_toolCallLogger.js';

/**
 * Send messages to the configured fallback provider (Anthropic by default).
 * @param {Array<{role: string, content: string}>} messages
 * @param {string} [systemPrompt]
 * @returns {Promise<{provider: string, model: string, content: string, fallbackTriggered: true}>}
 */
export async function runFallback(messages, systemPrompt = '') {
  if (!env.fallback.enabled) {
    throw new Error('Fallback is disabled. Set FALLBACK_ENABLED=true to enable.');
  }

  if (!env.fallback.apiKey) {
    throw new Error('Fallback requires ANTHROPIC_API_KEY to be set.');
  }

  if (!env.fallback.apiUrl) {
    throw new Error('Fallback requires FALLBACK_API_URL to be set.');
  }

  if (!env.fallback.model) {
    throw new Error('Fallback requires FALLBACK_MODEL to be set.');
  }

  try {
    const body = {
      model: env.fallback.model,
      max_tokens: 1200,
      messages: messages.slice(-10),
    };
    if (systemPrompt) body.system = systemPrompt;

    const response = await fetch(env.fallback.apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.fallback.apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(env.fallback.timeoutMs),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`${env.fallback.provider} error ${response.status}: ${errText}`);
    }

    const data = await response.json();
    const content = data?.content?.[0]?.text || '';

    logToolCall({
      source: 'quinnRouter',
      destination: env.fallback.provider,
      model: env.fallback.model,
      fallbackTriggered: true,
      status: 'success',
    });

    return {
      provider: env.fallback.provider,
      model: env.fallback.model,
      content,
      fallbackTriggered: true,
      source: 'fallback_direct',
    };
  } catch (error) {
    logToolCall({
      source: 'quinnRouter',
      destination: env.fallback.provider,
      model: env.fallback.model,
      fallbackTriggered: true,
      status: 'error',
      error: error.message,
    });
    throw error;
  }
}
