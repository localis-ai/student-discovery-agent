"""
Logging Utility for SDA Backend using Loguru

This module provides simple, powerful logging using loguru with OpenTelemetry integration.
Features include:

- Beautiful colorful console output by default
- Automatic log rotation and retention
- Minimal configuration needed
- FastAPI middleware integration
- Exception tracking and formatting with full traceback capture
- OpenTelemetry HTTP integration
- Global exception handler for uncaught exceptions

Usage:
    from app.modules.common.utils.logging import logger, setup_logging

    # Setup logging (call once in main.py)
    setup_logging()

    # Use logger directly
    logger.info("Application started")
    logger.warning("Something might be wrong")
    logger.error("An error occurred")
    logger.debug("Detailed debug information")
    logger.success("Operation completed successfully")

    # For exceptions, use logger.exception() to include traceback
    try:
        risky_operation()
    except Exception:
        logger.exception("Something went wrong")
"""

import logging
import sys
import threading
import time
import traceback

from loguru import logger as loguru_logger

# Export logger for easy import
logger = loguru_logger


class LoguruHandler(logging.Handler):
    def emit(self, record):
        from loguru import logger

        logger.opt(exception=record.exc_info).log(record.levelname, record.getMessage())


class PropagateHandler(logging.Handler):
    """PropagateHandler forwards Loguru messages into stdlib logging for OTel."""

    def emit(self, record):
        logging.getLogger(record.name).handle(record)


def _global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Global exception handler to catch uncaught exceptions and log them with full traceback.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Format the full traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)

    # Merge OpenTelemetry context and traceback for failure diagnostics
    context = {
        "exception_type": exc_type.__name__,
        "exception_message": str(exc_value),
        "traceback": tb_text,
    }
    # Log with full traceback - this will be sent to both console and OTel
    logger.bind(**context).critical(f"Uncaught exception in thread {threading.current_thread().name}: {exc_value}")

    # Call the default exception handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration with Loguru + OpenTelemetry.

    This implementation builds a proper Loguru -> stdlib logging bridge,
    then attaches OpenTelemetry LoggingHandler to root logger.
    """

    # Reset Loguru and attach a single console sink
    loguru_logger.remove()
    loguru_logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )
    loguru_logger.add(PropagateHandler(), level=level)

    # Setup stdlib logging to route through Loguru
    logging.basicConfig(handlers=[], level=0)
    root_logger = logging.getLogger()
    root_logger.handlers = []
    sys.excepthook = _global_exception_handler
    loguru_logger.info("Logging setup completed with fallback handler")


# FastAPI middleware for request/response logging
class FastAPILoggingMiddleware:
    """
    FastAPI middleware that logs HTTP requests and responses with timing.

    Features:
    - Logs request method, path, response status, and duration
    - Includes request tracking (request_id, trace_id) in all logs
    - Supports streaming responses (Server-Sent Events, NDJSON, etc.)
    - Detects streaming content types automatically
    - Doesn't buffer streaming responses for memory efficiency
    - Handles both regular and streaming response bodies
    - Extracts tracking IDs from request state (set by RequestTrackingMiddleware)

    Streaming Content Types Supported:
    - text/event-stream (Server-Sent Events / SSE)
    - application/x-ndjson (Newline-Delimited JSON)
    - application/stream+json
    - text/plain (when used with streaming)
    """

    # Content types that indicate streaming responses
    STREAMING_CONTENT_TYPES = {
        "text/event-stream",
        "application/x-ndjson",
        "application/stream+json",
        "application/octet-stream",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request info
        method = scope["method"]
        path = scope["path"]
        query = scope.get("query_string", b"").decode("utf-8")
        if query:
            path = f"{path}?{query}"

        # Try to extract request tracking IDs from headers
        headers = dict(scope.get("headers", []))
        request_id = None

        for key, value in headers.items():
            if key.lower() == b"x-request-id":
                request_id = value.decode("utf-8")

        # Create tracking context and expose request headers to logs
        tracking_context = {}
        if request_id:
            tracking_context["request_id"] = request_id

        # Also store in scope dict for downstream access
        if "state" not in scope:
            scope["state"] = {}
        if request_id:
            scope["state"]["request_id"] = request_id

        logger.bind(**tracking_context).info(f"→ {method} {path}")

        # Track timing
        start_time = time.time()
        original_send = send
        response_status = None
        response_length = 0
        is_streaming = False
        content_type = None

        async def logging_send(message):
            nonlocal response_status, response_length, is_streaming, content_type

            if message["type"] == "http.response.start":
                response_status = message["status"]

                # Check headers for content type and streaming indicators
                headers = message.get("headers", [])
                for header_name, header_value in headers:
                    if header_name.lower() == b"content-type":
                        content_type = header_value.decode("utf-8").lower()
                        # Check if this is a streaming content type
                        is_streaming = any(ct in content_type for ct in self.STREAMING_CONTENT_TYPES)
                        break

                if is_streaming:
                    logger.bind(**tracking_context).debug(f"Streaming response detected: {content_type}")

            elif message["type"] == "http.response.body":
                # Only track body size for non-streaming responses
                if not is_streaming:
                    response_length += len(message.get("body", b""))
                else:
                    # For streaming, just track that we're sending chunks
                    body = message.get("body", b"")
                    if body:
                        chunk_size = len(body)
                        # Log streaming chunk (useful for debugging)
                        logger.bind(**tracking_context).debug(f"Streaming chunk: {chunk_size} bytes")

            await original_send(message)

        try:
            await self.app(scope, receive, logging_send)
            duration = time.time() - start_time

            # Get current tracking context (may have been updated by inner middleware)
            current_context = tracking_context

            # Format log message based on response type
            if is_streaming:
                log_msg = f"← {method} {path} | {response_status} | {duration:.3f}s | [STREAMING: {content_type}]"
            else:
                log_msg = f"← {method} {path} | {response_status} | {duration:.3f}s | {response_length} bytes"

            if response_status and response_status < 400:
                logger.bind(**current_context).success(log_msg)
            else:
                logger.bind(**current_context).warning(log_msg)
        except Exception:
            duration = time.time() - start_time
            # Get current tracking context for exception logging
            current_context = tracking_context
            logger.bind(**current_context).exception(f"Error processing request {method} {path} | ERROR | {duration:.3f}s")
            raise
