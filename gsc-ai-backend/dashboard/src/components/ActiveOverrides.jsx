// ActiveOverrides.jsx
// Displays the list of currently active AI override rules as cards.
// Purely presentational — receives the overrides array and timestamps as props.

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function AiBadge() {
  return (
    <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-semibold text-purple-700">
      ⚙️ AI Active
    </span>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 bg-white py-12 text-center">
      <span className="mb-3 text-4xl">🤖</span>
      <p className="text-sm font-medium text-gray-500">No active overrides.</p>
      <p className="mt-1 text-xs text-gray-400">
        AI is running on the base system prompt.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * @param {{ overrides: Array<{ rule: string, addedAt: string }> }} props
 */
export default function ActiveOverrides({ overrides }) {
  if (!overrides || overrides.length === 0) {
    return <EmptyState />
  }

  return (
    <div className="flex flex-col gap-3">
      {overrides.map((item, index) => (
        <div
          key={index}
          className="flex items-start justify-between gap-4 rounded-xl bg-white p-4 shadow-sm"
        >
          {/* Left — rule number + text */}
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-600 text-xs font-bold text-white">
              {index + 1}
            </span>
            <p className="text-sm text-gray-700 leading-relaxed">{item.rule}</p>
          </div>

          {/* Right — badge + timestamp */}
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <AiBadge />
            <span className="text-xs text-gray-400">{item.addedAt}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
