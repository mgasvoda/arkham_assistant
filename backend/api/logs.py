"""Frontend logging endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.logging_config import get_logger

router = APIRouter()
logger = get_logger("frontend")


class FrontendLogEntry(BaseModel):
    """Log entry from frontend."""

    level: Literal["debug", "info", "warn", "error"] = Field(description="Log level")
    message: str = Field(description="Log message")
    component: str | None = Field(default=None, description="React component name")
    error_stack: str | None = Field(default=None, description="Error stack trace if available")
    user_agent: str | None = Field(default=None, description="Browser user agent")
    url: str | None = Field(default=None, description="Current page URL")
    extra: dict | None = Field(default=None, description="Additional context")


class FrontendLogBatch(BaseModel):
    """Batch of frontend log entries."""

    entries: list[FrontendLogEntry] = Field(description="Log entries")
    session_id: str | None = Field(default=None, description="Browser session ID for correlation")


@router.post("/")
async def receive_logs(batch: FrontendLogBatch) -> dict:
    """Receive log entries from frontend.

    Writes frontend logs to the frontend.log file with structured format.
    """
    for entry in batch.entries:
        log_level = getattr(logger, entry.level, logger.info)
        log_level(
            entry.message,
            extra={
                "extra_data": {
                    "source": "frontend",
                    "component": entry.component,
                    "session_id": batch.session_id,
                    "url": entry.url,
                    "error_stack": entry.error_stack,
                    **(entry.extra or {}),
                }
            },
        )

    return {"received": len(batch.entries)}
