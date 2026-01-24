# Arkham Assistant

A local hobby project to assist with *Arkham Horror: The Card Game* deckbuilding, testing, and tuning.

## Features

- 🃏 Card database with ChromaDB vector storage
- 🤖 AI-powered deck analysis and recommendations
- 🎲 Monte Carlo simulation engine for deck testing
- 💬 Chat-based interface for deckbuilding assistance
- 📊 Deck performance metrics and visualization

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 18 + Vite
- **Database**: ChromaDB
- **LLM Orchestration**: LangGraph with OpenAI

## Quick Start

### Environment Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-actual-key
   ```

3. (Optional) Configure model selection:
   ```
   ORCHESTRATOR_MODEL=gpt-4o      # Primary reasoning model
   SUBAGENT_MODEL=gpt-4o-mini     # Faster model for simple tasks
   ```

### Backend Setup

```bash
# Install dependencies with uv
uv sync

# Run development server
uv run uvicorn backend.main:app --reload
```

### Frontend Setup

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev
```

### Data Import

```bash
# Import card data from ArkhamDB
cd scripts
uv run python fetch_arkhamdb.py --full
```

## LLM Configuration

The assistant uses LangGraph with OpenAI models. Configuration is managed through environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `ORCHESTRATOR_MODEL` | No | `gpt-4o` | Model for complex reasoning (e.g., `o3`, `o4-mini`) |
| `SUBAGENT_MODEL` | No | `gpt-4o-mini` | Model for simple tasks (e.g., `gpt-5-mini`) |

The LLM configuration is centralized in `backend/services/llm_config.py`.

## Development

See `/docs` for detailed design documentation:
- `architecture_overview.md` - System design
- `backend/` - API, simulation, and AI agent designs
- `frontend/` - React component specifications

## Testing

```bash
# Backend tests
pytest

# Frontend unit tests
cd frontend && npm run test

# Frontend E2E tests
cd frontend && npm run test:e2e
```

## License

Personal hobby project - not for distribution.

