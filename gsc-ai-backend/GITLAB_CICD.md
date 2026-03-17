# GitLab CI/CD Setup Guide (GSC AI Backend)

This project now includes a GitLab pipeline in [.gitlab-ci.yml](.gitlab-ci.yml).

## What the pipeline does

1. backend_tests (required)
- Uses Python 3.12
- Installs requirements from requirements.txt
- Initializes SQLite seed data using mcp_server.database.connection.init_db()
- Runs pytest tests in tests/

2. dashboard_build (required)
- Uses Node 20
- Installs dashboard dependencies with npm ci
- Builds dashboard production assets
- Publishes dashboard/dist as an artifact

3. playwright_e2e_manual (optional/manual)
- Uses Playwright image
- Starts orchestrator server
- Runs Playwright specs
- Marked manual + allow_failure so it does not block normal CI

## One-time GitLab project configuration

1. Push your branch with these files to GitLab.

2. In GitLab, open:
- Settings > CI/CD > Variables

3. Add CI variables:
- OPENAI_API_KEY = your real OpenAI key
- OPENAI_MODEL = gpt-4o (or your preferred model)

Recommended variable settings:
- Masked: enabled for OPENAI_API_KEY
- Protected: enable only if you run protected branches/tags pipelines

4. Confirm you have at least one active runner:
- Settings > CI/CD > Runners
- If no shared runner is available, register a project runner.

## First pipeline run

1. Commit and push to your GitLab branch.
2. Open CI/CD > Pipelines.
3. Verify these jobs pass:
- backend_tests
- dashboard_build

4. Optional: trigger Playwright job manually
- Open pipeline
- Click the play button on playwright_e2e_manual

## Security and repository hygiene

1. Keep secrets out of git
- Use GitLab CI/CD variables for OPENAI_API_KEY
- Do not commit .env

2. Use the template env file
- Copy values from [.env.example](.env.example) to your local .env for local development only

3. If a real key was ever committed previously
- Rotate the OpenAI key immediately
- Replace it in GitLab CI variables and local .env

## Suggested branch protection flow

1. Configure protected branch for main.
2. Require passing pipeline before merge.
3. Keep playwright_e2e_manual optional (manual) initially.
4. Once stable, you can make Playwright required by removing when: manual and allow_failure: true.

## Troubleshooting

1. backend_tests fails with import/module errors
- Confirm pipeline runs from repo root where requirements.txt exists.

2. dashboard_build fails
- Check dashboard/package.json lock consistency.
- Re-run npm install locally, commit lockfile updates if needed.

3. Playwright manual job fails
- This is optional by design.
- Start by stabilizing backend and dashboard jobs first.
- Then tighten Playwright config (headless mode, deterministic mocks, API test doubles).
