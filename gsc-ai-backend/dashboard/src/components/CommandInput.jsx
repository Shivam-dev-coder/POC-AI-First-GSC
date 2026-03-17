// CommandInput.jsx
// Command Centre section — textarea, quick-command buttons, Apply/Clear
// actions, and toast notifications. Calls the orchestrator API directly.
//
// The Apply Rule button sends a plain-English command to POST /command.
// The AI classifies it as a rule override or a popup push and the toast
// reflects which path was taken.

import { useState, useEffect, useRef } from 'react'
import { sendCommand, clearAllOverrides } from '../api/orchestrator'

const QUICK_COMMANDS = [
  "Don't show location override popup on map screen",
  'Hard block Stop 4 — no override allowed',
  'Cigarettes must be scanned twice and manually counted',
  'All damaged items require a photo before delivery',
  'Driver ID 1 is new — enable spotlight guidance on all screens',
  'Clear all location restrictions',
  'Send a popup to all drivers: please check your next stop details',
  'Send urgent popup to all drivers: route has changed, check the app',
]

// ---------------------------------------------------------------------------
// Toast — three variants: success (green), info (blue), error (red)
// ---------------------------------------------------------------------------

function Toast({ toast }) {
  if (!toast) return null
  const styles = {
    success: 'bg-green-600',
    info:    'bg-blue-600',
    error:   'bg-red-600',
  }
  const icons = {
    success: '✅',
    info:    '📣',
    error:   '🗑️',
  }
  const colorClass = styles[toast.type] ?? styles.success
  const icon       = icons[toast.type]  ?? '✅'
  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-lg px-5 py-3 text-sm font-medium text-white shadow-lg transition-all duration-300 ${colorClass}`}
    >
      <span>{icon}</span>
      <span>{toast.message}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CommandInput
// ---------------------------------------------------------------------------

export default function CommandInput({ onRuleApplied }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  // Clear any lingering timer on unmount
  useEffect(() => () => clearTimeout(toastTimer.current), [])

  function showToast(message, type) {
    setToast({ message, type })
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 4000)
  }

  async function handleApply() {
    const command = text.trim()
    if (!command) return
    setLoading(true)
    try {
      const res = await sendCommand(command)

      if (res.type === 'override') {
        showToast('Rule applied — AI updated', 'success')
        onRuleApplied?.()
      } else if (res.type === 'popup') {
        const reached      = res.reached ?? []
        const notConnected = res.not_connected ?? []
        let msg = `Popup sent to ${reached.length} driver${reached.length !== 1 ? 's' : ''}`
        if (notConnected.length > 0) {
          msg += ` (${notConnected.length} not connected)`
        }
        showToast(msg, 'info')
        // Do NOT call onRuleApplied — no override was added
      }

      setText('')
    } catch (err) {
      showToast(`Failed: ${err.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleClear() {
    if (!window.confirm('Remove all active override rules? The AI will revert to the base system prompt.')) return
    setLoading(true)
    try {
      await clearAllOverrides()
      showToast('All rules cleared', 'error')
      onRuleApplied?.()
    } catch (err) {
      showToast(`Failed: ${err.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl bg-white p-6 shadow-sm">
      {/* Quick command buttons */}
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
        Quick Commands
      </p>
      <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {QUICK_COMMANDS.map((cmd) => (
          <button
            key={cmd}
            onClick={() => setText(cmd)}
            className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs text-gray-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
          >
            {cmd}
          </button>
        ))}
      </div>

      {/* Textarea */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a rule or popup command… e.g. 'Hard block Stop 4' or 'Send a popup to all drivers: traffic ahead'"
        rows={4}
        className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-800 placeholder-gray-400 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
      />

      {/* Action buttons */}
      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={handleApply}
          disabled={loading || !text.trim()}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? '⏳' : '⚡'} Apply
        </button>
        <button
          onClick={handleClear}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          🗑️ Clear All Rules
        </button>
      </div>

      <Toast toast={toast} />
    </div>
  )
}
