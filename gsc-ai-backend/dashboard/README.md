# GSC AI Dashboard

Real-time control panel for the GSC AI Orchestrator. Inject plain-English rules
into the AI's live system prompt, monitor live intent traffic from Flutter, and
inspect the active rule set — all from one page.

## Prerequisites

- Node.js 18+ and npm
- GSC AI Orchestrator running on `http://localhost:8000`

## Install

```bash
cd gsc-ai-backend/dashboard
npm install
```

## Run

```bash
npm run dev
```

Dashboard is available at **http://localhost:5173**

## Build for production

```bash
npm run build    # outputs to dashboard/dist/
npm run preview  # serves the production build locally
```

## Components

| File | What it does |
|---|---|
| `src/App.jsx` | Root component — owns overrides state, renders sidebar and all sections |
| `src/components/CommandInput.jsx` | Textarea + quick-command buttons + Apply/Clear actions + toast notifications |
| `src/components/ActiveOverrides.jsx` | Read-only list of currently active AI override rule cards |
| `src/components/LiveLog.jsx` | Auto-reconnecting WebSocket feed of Flutter intents and AI responses |
| `src/components/SystemPrompt.jsx` | Read-only dark code block showing the AI base system prompt |
| `src/api/orchestrator.js` | Fetch wrappers for POST /override, DELETE /overrides, GET /overrides |

## API endpoints used

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/overrides` | Fetch current active override rules |
| `POST` | `/override` | Add a new rule to the AI prompt |
| `DELETE` | `/overrides` | Clear all active rules |
| `WS` | `/ws/log` | Stream live intent + response events for the Live Log section |

## Dev proxy

All `/api/*` calls and `/ws/*` WebSocket connections are proxied by Vite to
`http://localhost:8000` so no CORS configuration is needed during development.
See `vite.config.js` for details.
