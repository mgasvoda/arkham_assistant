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
- **LLM**: OpenAI GPT-5 or local model

## Quick Start

### Backend Setup

```bash
# Install dependencies with uv
cd backend
uv sync

# Run development server
uv run uvicorn main:app --reload
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

