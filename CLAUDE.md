# Arkham Assistant - Claude Code Context

## Commands
- `uv run pytest tests/` - Run tests (NOT python -m pytest)
- `uv run pytest tests/ -k "pattern"` - Run specific tests
- `uv run pytest --cov=backend --cov-report=html` - Run with coverage
- `uv run ruff check backend/` - Lint code
- `uv run ruff check --fix backend/` - Auto-fix lint issues
- `uv run ruff format backend/` - Format code
- `uv add <package>` - Add dependencies
- `uv sync` - Update dependencies

## Architecture
- Subagents in `backend/services/subagents/` - RulesAgent, ScenarioAgent, StateAgent, ActionSpaceAgent
- All response types extend `SubagentResponse` and implement `_get_error_defaults()` hook
- Common utilities in `backend/services/subagents/utils.py` (CardDataLoader, classify_query_by_keywords, compute_bounded_confidence)
- LangGraph used for LLM-powered agents (RulesAgent, ScenarioAgent)
- Analysis-only agents (StateAgent, ActionSpaceAgent) don't use LLM

## Patterns
- Use `CardDataLoader` for card input normalization and JSON field parsing
- Query type classification uses keyword patterns dict with `classify_query_by_keywords()`
- Confidence scoring uses `compute_bounded_confidence()` with adjustments list

## Code Quality
- Major functionality MUST have basic tests covering core behavior
- Prefer utility functions in dedicated modules over inline implementations
- Extract and generalize repeated logic into reusable utility functions
- Keep functions focused and single-purpose
- Use type hints for function signatures
- Follow PEP 8 conventions (enforced by ruff)

## Documentation Policy
- **DO NOT** create new markdown/documentation files unless explicitly instructed
- When modifying functionality, update relevant docs in `/docs`:
  - `frontend_design.md` - React components, UI, API integration
  - `ai_agent_design.md` - AI agent tools, prompts, conversation flows
  - `simulation_design.md` - Simulation engine, metrics, algorithms
  - `database_crud_design.md` - ChromaDB schema, CRUD operations, data models
  - `data_retrieval_design.md` - ArkhamDB API integration, data import
  - `architecture_overview.md` - System-wide architectural changes
- Keep documentation updates concise and focused on material changes

## Testing
- Pydantic models that extend SubagentResponse require `content` and `metadata` fields in tests
- Integration tests use real ChromaDB; unit tests use mocks
- Test files: `tests/test_<module_name>.py`
- Test functions: `test_<function_name>_<scenario>`
- Coverage goals: 80%+ for core business logic
- Tests should be fast (mock external dependencies) and isolated (no shared state)

### Frontend Testing
- **Vitest** for React component and utility tests
- **Playwright** for E2E tests with console error detection
- E2E tests MUST verify no console errors
- Run: `npm run test` (unit), `npm run test:e2e` (E2E)

### Manual API Testing
For testing API endpoints locally:

1. **Start the backend server** (in separate terminal or background):
   ```bash
   uv run uvicorn backend.main:app --reload
   ```

2. **Populate ChromaDB with test data** (required for card/investigator queries):
   ```bash
   uv run python scripts/fetch_arkhamdb.py --pack core
   ```

3. **Test endpoints with curl**:
   ```bash
   # Health check
   curl -s http://localhost:8000/health

   # Q&A request
   curl -X POST http://localhost:8000/chat/ \
     -H "Content-Type: application/json" \
     -d '{"message": "What cards can Roland Banks include?"}'

   # Deck building request
   curl -X POST http://localhost:8000/chat/ \
     -H "Content-Type: application/json" \
     -d '{"message": "Build me a combat deck", "investigator_id": "01001", "investigator_name": "Roland Banks"}'
   ```

4. **View API docs**: http://localhost:8000/docs

Note: The trailing slash on `/chat/` is required (FastAPI redirects without it). The user must first populate a .env with the OPENAI API KEY
