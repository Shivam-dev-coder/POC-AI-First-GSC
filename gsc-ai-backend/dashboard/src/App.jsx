// App.jsx
// Root component — renders the sidebar and all four main sections, owns the
// overrides state and passes refresh callbacks down to child components.

import { useState, useEffect, useCallback } from 'react'
import CommandInput from './components/CommandInput'
import ActiveOverrides from './components/ActiveOverrides'
import LiveLog from './components/LiveLog'
import SystemPrompt from './components/SystemPrompt'
import { getOverrides } from './api/orchestrator'

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

const NAV_LINKS = [
  { href: '#overview',         label: '📊 Overview' },
  { href: '#command-centre',   label: '⚡ Command Centre' },
  { href: '#active-overrides', label: '🔀 Active Overrides' },
  { href: '#live-log',         label: '📡 Live Log' },
  { href: '#system-prompt',    label: '🤖 System Prompt' },
]

function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 flex h-screen w-60 flex-col bg-[#111827] px-5 py-8">
      <div className="mb-8">
        <h1 className="text-lg font-bold text-white">🚚 GSC AI Dashboard</h1>
        <p className="mt-1 text-xs text-gray-400">Delivery Logic Control Panel</p>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_LINKS.map(({ href, label }) => (
          <a
            key={href}
            href={href}
            className="rounded-lg px-3 py-2 text-sm text-gray-300 transition hover:bg-gray-700 hover:text-white"
          >
            {label}
          </a>
        ))}
      </nav>
      <div className="mt-auto pt-8 text-xs text-gray-600">
        Orchestrator · localhost:8000
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Overview stat cards
// ---------------------------------------------------------------------------

function useClock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(id)
  }, [])
  return time
}

function StatCard({ icon, label, value, valueClass = 'text-gray-800' }) {
  return (
    <div className="flex flex-1 items-center gap-4 rounded-xl bg-white p-5 shadow-sm">
      <span className="text-3xl">{icon}</span>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{label}</p>
        <p className={`mt-0.5 text-2xl font-bold ${valueClass}`}>{value}</p>
      </div>
    </div>
  )
}

function OverviewSection({ overrideCount, isOnline }) {
  const time = useClock()
  return (
    <section id="overview" className="scroll-mt-6">
      <SectionHeading title="Overview" />
      <div className="flex flex-col gap-4 sm:flex-row">
        <StatCard icon="🔀" label="Active Overrides" value={overrideCount} />
        <StatCard
          icon={isOnline ? '🟢' : '🔴'}
          label="Orchestrator"
          value={isOnline ? 'Online' : 'Offline'}
          valueClass={isOnline ? 'text-green-600' : 'text-red-600'}
        />
        <StatCard icon="🕐" label="Current Time" value={time} />
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------

function SectionHeading({ title }) {
  return (
    <h2 className="mb-4 text-lg font-semibold text-gray-700">{title}</h2>
  )
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  // overrides: Array<{ rule: string, addedAt: string }>
  const [overrides, setOverrides] = useState([])
  const [isOnline, setIsOnline] = useState(false)

  const refreshOverrides = useCallback(async () => {
    try {
      const data = await getOverrides()
      setIsOnline(true)
      // Preserve existing addedAt timestamps for rules already in state;
      // stamp new rules with the current time.
      setOverrides((prev) => {
        const prevMap = Object.fromEntries(prev.map((o) => [o.rule, o.addedAt]))
        return (data.overrides ?? []).map((rule) => ({
          rule,
          addedAt: prevMap[rule] ?? new Date().toLocaleTimeString(),
        }))
      })
    } catch {
      setIsOnline(false)
    }
  }, [])

  // Fetch on mount to populate overview count and override list
  useEffect(() => {
    refreshOverrides()
  }, [refreshOverrides])

  return (
    <div className="min-h-screen bg-[#F3F4F6]">
      <Sidebar />

      {/* Main content — offset by sidebar width */}
      <main className="ml-60 flex flex-col gap-10 px-8 py-8">

        <OverviewSection
          overrideCount={overrides.length}
          isOnline={isOnline}
        />

        <section id="command-centre" className="scroll-mt-6">
          <SectionHeading title="Command Centre" />
          <CommandInput onRuleApplied={refreshOverrides} />
        </section>

        <section id="active-overrides" className="scroll-mt-6">
          <SectionHeading title="Active Overrides" />
          <ActiveOverrides overrides={overrides} />
        </section>

        <section id="live-log" className="scroll-mt-6">
          <SectionHeading title="Live Log" />
          <LiveLog />
        </section>

        <section id="system-prompt" className="scroll-mt-6 pb-10">
          <SectionHeading title="System Prompt" />
          <SystemPrompt />
        </section>

      </main>
    </div>
  )
}
