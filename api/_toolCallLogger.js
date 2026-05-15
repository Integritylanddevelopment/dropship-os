// ============================================================
// api/_toolCallLogger.js — Structured tool-call logging
//
// Edge Runtime does not support fs. Logs are written as structured
// JSON to console (captured by Vercel log drain / platform logs).
// For local Python bridge logging, use the bridge's own log file.
// ============================================================

/**
 * @typedef {Object} ToolCallEntry
 * @property {string} source          - Caller identifier
 * @property {string} destination     - Target system (quinn | anthropic | ...)
 * @property {string} model           - Model name used
 * @property {boolean} fallbackTriggered
 * @property {'success'|'error'} status
 * @property {string} [error]
 */

/**
 * Log a tool call as a structured JSON line.
 * @param {ToolCallEntry} entry
 */
export function logToolCall(entry) {
  const record = {
    timestamp: new Date().toISOString(),
    ...entry,
  };
  // Structured log — captured by Vercel log drain and local console
  console.log('[tool-call]', JSON.stringify(record));
}
