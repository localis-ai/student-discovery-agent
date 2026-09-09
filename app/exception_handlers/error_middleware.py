"""
Middleware to catch and standardize error responses for unhandled exceptions.

This middleware:
1. Catches all unhandled exceptions during request processing
2. Converts them to standardized error responses with proper status codes
3. Logs exceptions with request tracking (request_id, trace_id)
4. Ensures all error responses include: status, success, error (with code/message/retryable), meta
"""

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.modules.common.utils.logging import logger
from app.modules.common.utils.response import error_response, get_request_id, get_trace_id


class ErrorStandardizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that catches unhandled exceptions and converts them to standardized error responses.

    Features:
    - Catches all unhandled exceptions from route handlers
    - Converts to standardized error response format with status, success, error, meta
    - Error includes: code, message, retryable, details
    - Logs exception with request tracking
    - Preserves HTTP status codes as much as possible
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Get request tracking information
            request_id = get_request_id()
            trace_id = get_trace_id()

            if hasattr(request.state, "request_id"):
                request_id = request.state.request_id
            if hasattr(request.state, "trace_id"):
                trace_id = request.state.trace_id

            # Log the unhandled exception
            logger.exception(
                f"Unhandled exception in {request.method} {request.url.path}: {type(exc).__name__}",
                extra={
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "exception_type": type(exc).__name__,
                    "path": request.url.path,
                },
            )

            # Create standardized error response
            error_resp = error_response(
                status_code=500,
                error_code="SYS_INTERNAL_ERROR",
                error_message="Internal server error",
                retryable=True,
                details={"exception": type(exc).__name__},
                request_id=request_id,
                trace_id=trace_id,
            )

            return JSONResponse(
                status_code=500,
                content=error_resp.model_dump(),
            )
