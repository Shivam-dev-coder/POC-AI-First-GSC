// api/orchestrator.js
// Thin fetch wrapper for all REST calls to the AI Orchestrator.
// All requests go through the Vite dev proxy (/api → http://localhost:8000).

const BASE = '/api'

/**
 * Shared fetch helper — throws a descriptive Error on non-2xx responses
 * so callers can catch and surface the message in the UI.
 */
async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? body.error ?? detail
    } catch {
      // ignore parse errors — use the status string
    }
    throw new Error(detail)
  }

  // 204 No Content — return null instead of trying to parse an empty body
  if (res.status === 204) return null

  return res.json()
}

/**
 * POST /command
 * Unified Command Centre endpoint. Sends a plain-English command to the AI.
 * The AI classifies it as either a rule override or a popup push and acts.
 *
 * @param {string} commandText  - the raw text from the Command Centre textarea
 * @returns {Promise<
 *   | { type: 'override', rule: string }
 *   | { type: 'popup', status: string, target: string, reached: number[], not_connected: number[] }
 * >}
 */
export async function sendCommand(commandText) {
  return request('/command', {
    method: 'POST',
    body: JSON.stringify({ command: commandText }),
  })
}

/**
 * DELETE /overrides
 * Removes all active override rules and restores the base system prompt.
 * @returns {Promise<{ status: string }>}
 */
export async function clearAllOverrides() {
  return request('/overrides', { method: 'DELETE' })
}

/**
 * GET /overrides
 * Returns the current list of active override rule strings.
 * @returns {Promise<{ overrides: string[] }>}
 */
export async function getOverrides() {
  return request('/overrides')
}

/**
 * GET /drivers/online
 * Returns driver IDs that currently have an active WebSocket connection.
 * @returns {Promise<{ driver_ids: number[] }>}
 */
export async function getOnlineDrivers() {
  return request('/drivers/online')
}
