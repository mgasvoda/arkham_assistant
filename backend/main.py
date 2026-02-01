"""Main FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import cards, characters, chat, decks, logs, sim
from backend.core.logging_config import get_logger, setup_logging
from backend.middleware.logging_middleware import RequestLoggingMiddleware

# Initialize logging before anything else
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    enable_console=True,
    enable_file=True,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Arkham Assistant API starting up")
    yield
    logger.info("Arkham Assistant API shutting down")


app = FastAPI(
    title="Arkham Assistant API",
    description="Backend API for Arkham Horror LCG deckbuilding assistant",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions globally.

    Logs the error and returns a 500 response with a generic message.
    This catches any unhandled exceptions that slip through endpoint handlers.
    """
    logger.error(
        f"Unhandled exception for {request.url}",
        extra={"extra_data": {"path": str(request.url), "error_type": type(exc).__name__}},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# Add logging middleware BEFORE CORS
app.add_middleware(RequestLoggingMiddleware)

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
app.include_router(logs.router, prefix="/logs", tags=["logs"])


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
