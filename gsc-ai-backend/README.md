# GSC AI Backend

POC backend platform for the GSC delivery assistant.

This repository contains three main parts:

- AI orchestrator built with FastAPI and WebSockets
- MCP server that exposes delivery, stop, and inventory tools over SQLite data
- React dashboard used to manage live overrides and monitor orchestration traffic

## Repository Structure

- `orchestrator/` - FastAPI app, intent routing, prompt management, OpenAI reasoning
- `mcp_server/` - MCP tool server and SQLite-backed delivery data access
- `dashboard/` - Vite + React operations dashboard
- `tests/` - Python unit tests
- `specs/` - Playwright UI and integration specs
- `GITLAB_CICD.md` - GitLab CI/CD setup and pipeline usage

## Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- npm
- OpenAI API key

## Environment Setup

Create a local `.env` file from `.env.example`.

Required values:

- `DATABASE_URL=gsc_poc.db`
- `OPENAI_API_KEY=your_key_here`
- `OPENAI_MODEL=gpt-4o`

Do not commit `.env`. GitLab CI/CD should use project variables instead.

## Install Dependencies

Backend:

```bash
pip install -r requirements.txt
```

Dashboard:

```bash
npm --prefix dashboard install
```

## Run Locally

Start the MCP server:

```bash
python -m mcp_server.server
```

Start the orchestrator API:

```bash
python -m uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the dashboard:

```bash
npm --prefix dashboard run dev
```

Local endpoints:

- Orchestrator API: `http://localhost:8000`
- Dashboard: `http://localhost:5173`
- Driver WebSocket: `ws://localhost:8000/ws`
- Dashboard live log WebSocket: `ws://localhost:8000/ws/log`

## Run Tests

Python unit tests:

```bash
python -c "from mcp_server.database.connection import init_db; init_db()"
pytest -q tests
```

Dashboard production build:

```bash
npm --prefix dashboard run build
```

Playwright specs:

```bash
npx playwright test --config playwright.config.ts
```

Note: some Playwright tests expect the orchestrator and dashboard to be running, and some flows may depend on OpenAI-backed behavior.

## GitLab CI/CD

This repository includes a GitLab pipeline file:

- `.gitlab-ci.yml`

Pipeline stages:

- `backend_tests` - installs Python deps, initializes DB, runs pytest
- `dashboard_build` - installs dashboard deps and builds production assets
- `playwright_e2e_manual` - optional manual Playwright stage

Full GitLab setup steps are documented in `GITLAB_CICD.md`.

## API Summary

Main REST endpoints:

- `POST /override` - add a live prompt override
- `GET /overrides` - list active overrides
- `DELETE /overrides` - clear active overrides
- `GET /drivers/online` - list connected driver IDs
- `POST /command` - classify dashboard command as override or popup

WebSocket endpoints:

- `/ws` - Flutter driver app connection
- `/ws/log` - dashboard live log feed

## Notes

- SQLite data is seeded from `mcp_server/database/connection.py`
- The orchestrator uses OpenAI for reasoning and dashboard command classification
- The current setup is a POC, not a production deployment architecture