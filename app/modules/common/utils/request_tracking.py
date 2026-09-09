"""
FastAPI middleware for request tracking (request_id, trace_id).

This middleware:
1. Generates/extracts request_id and trace_id from headers or creates new ones
2. Stores them in context variables for use in response building
3. Adds them to response headers for client tracking
"""

import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.modules.common.utils.response import set_request_context


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request tracking (request_id, trace_id) to all requests.

    - Extracts or generates request_id and trace_id
    - Stores in context variables for use in response building
    - Adds headers to response headers for client tracking
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract request_id from header or generate new one
        request_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id") or str(uuid.uuid4())

        # Extract trace_id from header or generate new one
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("x-trace-id") or request.headers.get("X-B3-TraceId") or request.headers.get("x-b3-traceid") or str(uuid.uuid4())

        # Store in context for use in response building
        set_request_context(request_id, trace_id)

        # Add to request state for direct access if needed
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Call next middleware/route handler
        response = await call_next(request)

        # Add tracking headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id

        return response
