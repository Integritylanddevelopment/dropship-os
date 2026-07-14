// ============================================================
// api/_fallbackController.js — Quinn bridge fallback (Quinn-failed path)
//
// Only called when Quinn bridge is unreachable or returns an error.
// All config comes from environment variables via _config.js.
// ============================================================

import { env } from './_config.js';
import { logToolCall } from './_toolCallLogger.js';

/**
 * Send messages to Quinn bridge fallback (Rule 1: Quinn-only routing).
 * @param {Array<{role: string, content: string}>} messages
 * @param {string} [systemPrompt]
 * @returns {Promise<{provider: string, model: string, content: string, fallbackTriggered: true}>}
 */
export async function runFallback(messages, systemPrompt = '') {
  if (!env.fallback.enabled) {
    throw new Error('Fallback is disabled. Set FALLBACK_ENABLED=true to enable.');
  }

  try {
    const trimmedMessages = messages.slice(-10);
    const quinnUrl = process.env.QUINN_BRIDGE_URL || 'http://127.0.0.1:8765';
    const response = await fetch(`${quinnUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: env.fallback.model || 'qwen2.5:7b',
        messages: systemPrompt ? [{ role: 'system', content: systemPrompt }, ...trimmedMessages] : trimmedMessages,
        max_tokens: 1200,
      }),
      signal: AbortSignal.timeout(env.fallback.timeoutMs),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Quinn bridge error ${response.status}: ${errText}`);
    }

    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content || data?.content?.[0]?.text || '';

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
