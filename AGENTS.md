# Codex Agent Guidelines

Guidelines synthesized from `.cursor/rules` for day-to-day work in this repository.

## Core Project Standards

- Ship well-factored code: keep functions single-purpose, extract repeated logic into helpers, and prefer utilities over inline duplication.
- Give every significant feature at least a smoke-level test that lives beside related code in the matching `tests/` path.
- Use descriptive names and shallow control flow; break apart deep nesting with helpers.

## Documentation Discipline

- Never add new markdown/docs unless the user explicitly requests it (this file is user-requested). Update the existing design docs in `docs/` whenever functionality changes:
  - API endpoints → `docs/architecture_overview.md`
  - Database schema → `docs/database_crud_design.md`
  - AI agent tooling → `docs/ai_agent_design.md`
  - Simulation metrics/logic → `docs/simulation_design.md`
  - Frontend components or flows → `docs/frontend_design.md`
  - Data import processes → `docs/data_retrieval_design.md`
- Keep doc edits concise, match existing formatting, and refresh any impacted code snippets or examples.

## Python Development (backend, scripts, tests)

- Dependency management must go through `uv` (`uv add`, `uv sync`, `uv run`). Keep versions pinned in `pyproject.toml` and document notable libs in the relevant design doc.
- Lint and format exclusively with `ruff` (`ruff check .`, `ruff check --fix .`, `ruff format .`). All files must be clean before delivery.
- Follow PEP 8, use type hints on public functions, and favor explicit, descriptive naming.
- Tests: use `pytest`, store files under `tests/` mirroring the source tree, and name files/functions `test_<target>.py` / `test_<function>_<scenario>()`. Prefer fixtures for shared setup.

## JavaScript / React Testing

- Unit tests run with **Vitest** + `@testing-library/react`. Mock APIs/external deps and keep tests fast.
- End-to-end coverage runs with **Playwright** after major UI/API changes. Tests must monitor browser console output and fail on warnings/errors.
- Recommended scripts (`package.json`): `test` (Vitest), `test:e2e`, `test:e2e:ci`, and `test:all` that chains unit + e2e + linting. Ensure these stay accurate when tooling changes.

## Backend & Tooling Test Expectations

- Write tests for API endpoints, business logic (simulation, deck analysis), ArkhamDB→Chroma transforms, database CRUD, AI agent tools, and cross-module utilities.
- Maintain the sample structure under `tests/backend` (API folders, simulator, chroma client, etc.) and `tests/scripts` for data utilities.
- Aim for ≥80% coverage on core logic, cover happy/error paths, isolate tests with fixtures/mocks, and keep them fast.
- Standard commands: `pytest` (or targeted files) and `pytest --cov=backend --cov-report=html` for coverage runs.

## Frontend E2E Console Monitoring Pattern

- Attach Playwright listeners for both `page.on('console', …)` and `page.on('pageerror', …)`; fail the test when any error/warning appears.
- Wait for `networkidle`, assert key selectors (e.g., `data-testid` hooks), and keep interactions user-centric rather than implementation-specific.
- Treat console noise as regressions; fix before merging.

## When Updating Documentation vs. Code

- Touch doc files listed above whenever code changes affect their domain; otherwise rely on inline comments/docstrings.
- Do not create alternative documentation locations or rename existing files without explicit direction.
