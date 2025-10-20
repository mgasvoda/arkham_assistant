"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import cards, characters, chat, decks, sim

app = FastAPI(
    title="Arkham Assistant API",
    description="Backend API for Arkham Horror LCG deckbuilding assistant",
    version="0.1.0",
)

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cards.router, prefix="/cards", tags=["cards"])
app.include_router(characters.router, prefix="/characters", tags=["characters"])
app.include_router(decks.router, prefix="/decks", tags=["decks"])
app.include_router(sim.router, prefix="/sim", tags=["simulation"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Arkham Assistant API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

