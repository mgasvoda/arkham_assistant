"""Centralized logging configuration for Arkham Assistant."""

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Project root for log directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds context to all log messages."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        extra["extra_data"] = {**self.extra, **extra.get("extra_data", {})}
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_file: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        enable_console: Whether to log to console.
        enable_file: Whether to log to files.
        max_bytes: Maximum size per log file before rotation.
        backup_count: Number of backup files to keep.
    """
    # Create logs directory
    LOG_DIR.mkdir(exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (human-readable format)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handlers (JSON format for structured parsing)
    if enable_file:
        json_formatter = JSONFormatter()

        # Main application log
        app_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "arkham_assistant.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(json_formatter)
        root_logger.addHandler(app_handler)

        # Error-only log for quick debugging
        error_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "errors.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        root_logger.addHandler(error_handler)

        # Agent-specific log
        agent_logger = logging.getLogger("backend.services")
        agent_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "agents.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        agent_handler.setLevel(logging.DEBUG)
        agent_handler.setFormatter(json_formatter)
        agent_logger.addHandler(agent_handler)

        # Frontend log
        frontend_logger = logging.getLogger("frontend")
        frontend_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "frontend.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        frontend_handler.setLevel(logging.DEBUG)
        frontend_handler.setFormatter(json_formatter)
        frontend_logger.addHandler(frontend_handler)


def get_logger(name: str, **context: Any) -> ContextLogger:
    """Get a logger with optional context.

    Args:
        name: Logger name (typically __name__).
        **context: Additional context to include in all log messages.

    Returns:
        ContextLogger with the specified context.
    """
    logger = logging.getLogger(name)
    return ContextLogger(logger, context)
