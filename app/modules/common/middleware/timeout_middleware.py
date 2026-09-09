"""
Timeout Middleware for Backend API

Handles timeout exceptions and converts them to standardized error responses.
"""

import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.modules.common.utils.response import error_response, get_request_id, get_trace_id
from app.modules.common.utils.timeout_utils import TimeoutException


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle timeout exceptions and convert to standardized responses.

    This middleware:
    1. Tracks request execution time
    2. Catches TimeoutException and converts to standardized error response
    3. Logs timeout events with request tracking
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        """
        Process request and handle timeouts.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response or error response if timeout occurs
        """
        start_time = time.time()
        request.state.start_time = start_time

        try:
            response = await call_next(request)
            return response

        except TimeoutException as e:
            # Calculate elapsed time
            elapsed_ms = (time.time() - start_time) * 1000

            # Get request tracking IDs
            request_id = get_request_id()
            trace_id = get_trace_id()

            if hasattr(request.state, "request_id"):
                request_id = request.state.request_id
            if hasattr(request.state, "trace_id"):
                trace_id = request.state.trace_id

            # Build standardized error response
            error_resp = error_response(
                status_code=e.status_code,
                error_code=e.error_code,
                error_message=e.message,
                retryable=e.retryable,
                details={
                    **(e.details or {}),
                    "elapsed_ms": elapsed_ms,
                },
                request_id=request_id,
                trace_id=trace_id,
            )

            # Return JSON response with proper status code
            return JSONResponse(
                status_code=e.status_code,
                content=error_resp.model_dump(),
                headers={
                    "X-Request-ID": request_id,
                    "X-Trace-ID": trace_id,
                },
            )
