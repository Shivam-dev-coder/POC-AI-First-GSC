// LiveLog.jsx
// Scrolling real-time feed of Flutter intent packets and AI responses.
// Manages its own WebSocket connection to /ws/log with auto-reconnect.

import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `ws://${window.location.host}/ws/log`
const MAX_ENTRIES = 100
const RECONNECT_DELAY_MS = 3000

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Determine the entry type from the raw message object. */
function classifyEntry(data) {
  if (data.error) return 'error'
  if (data.direction === 'in') return 'inbound'   // Flutter → AI
  if (data.direction === 'out') return 'outbound'  // AI → Flutter
  return 'inbound'
}

const BORDER_CLASS = {
  inbound:  'border-l-4 border-blue-400',
  outbound: 'border-l-4 border-purple-400',
  error:    'border-l-4 border-red-400',
}

const LABEL = {
  inbound:  { text: 'Flutter → AI',  cls: 'bg-blue-100 text-blue-700' },
  outbound: { text: 'AI → Flutter',  cls: 'bg-purple-100 text-purple-700' },
  error:    { text: 'Error',          cls: 'bg-red-100 text-red-700' },
}

// ---------------------------------------------------------------------------
// LogEntry — single collapsible row
// ---------------------------------------------------------------------------

function LogEntry({ entry }) {
  const [open, setOpen] = useState(false)
  const type = entry.type
  const label = LABEL[type]

  return (
    <div className={`rounded-lg bg-white px-4 py-3 shadow-sm ${BORDER_CLASS[type]}`}>
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${label.cls}`}>
            {label.text}
          </span>
          <span className="truncate text-sm font-medium text-gray-700">
            {entry.event ?? 'unknown'}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs text-gray-400">{entry.timestamp}</span>
          <button
            onClick={() => setOpen((o) => !o)}
            className="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            {open ? '▲ hide' : '▼ json'}
          </button>
        </div>
      </div>

      {/* Collapsible JSON payload */}
      {open && (
        <pre className="json-block mt-3 max-h-60 overflow-y-auto scrollbar-thin rounded-lg bg-gray-900 p-3 text-green-300">
          {JSON.stringify(entry.payload, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Connection status badge
// ---------------------------------------------------------------------------

const STATUS_STYLE = {
  connected:    'bg-green-100 text-green-700',
  disconnected: 'bg-gray-100 text-gray-500',
  error:        'bg-red-100 text-red-700',
  reconnecting: 'bg-yellow-100 text-yellow-700',
}

const STATUS_LABEL = {
  connected:    '🟢 Connected',
  disconnected: '⚪ Disconnected',
  error:        '🔴 Error',
  reconnecting: '🟡 Reconnecting…',
}

// ---------------------------------------------------------------------------
// LiveLog
// ---------------------------------------------------------------------------

export default function LiveLog() {
  const [entries, setEntries] = useState([])
  const [status, setStatus] = useState('disconnected')
  const bottomRef = useRef(null)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const unmounted = useRef(false)

  const connect = useCallback(() => {
    if (unmounted.current) return

    setStatus('reconnecting')

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      if (unmounted.current) return
      setStatus('connected')
    }

    ws.onmessage = (event) => {
      if (unmounted.current) return
      let data
      try {
        data = JSON.parse(event.data)
      } catch {
        data = { error: 'Unparseable message', raw: event.data }
      }

      const entry = {
        id: crypto.randomUUID(),
        timestamp: new Date().toLocaleTimeString(),
        type: classifyEntry(data),
        event: data.intent ?? data.event ?? (data.error ? 'error' : 'response'),
        payload: data,
      }

      setEntries((prev) => {
        const next = [...prev, entry]
        return next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next
      })
    }

    ws.onerror = () => {
      if (unmounted.current) return
      setStatus('error')
    }

    ws.onclose = () => {
      if (unmounted.current) return
      setStatus('disconnected')
      // Auto-reconnect after delay
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS)
    }
  }, [])

  // Mount: open connection. Unmount: close cleanly.
  useEffect(() => {
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  // Auto-scroll to bottom whenever entries change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries])

  function clearLog() {
    setEntries([])
  }

  return (
    <div className="rounded-xl bg-white shadow-sm overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[status]}`}>
            {STATUS_LABEL[status]}
          </span>
          <span className="text-xs text-gray-400">{entries.length} entries</span>
        </div>
        <button
          onClick={clearLog}
          className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-gray-500 transition hover:border-gray-300 hover:text-gray-700"
        >
          Clear Log
        </button>
      </div>

      {/* Feed */}
      <div className="flex h-96 flex-col gap-2 overflow-y-auto scrollbar-thin bg-gray-50 p-4">
        {entries.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <span className="mb-2 text-3xl">📡</span>
            <p className="text-sm text-gray-400">
              {status === 'connected'
                ? 'Waiting for events from Flutter…'
                : 'Connecting to orchestrator log stream…'}
            </p>
          </div>
        ) : (
          entries.map((entry) => <LogEntry key={entry.id} entry={entry} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
