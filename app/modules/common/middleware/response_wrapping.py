"""
Global Response Wrapping Middleware

Automatically transforms all API responses to standardized format:
{
  "status": <http_status>,
  "success": true/false,
  "data": <response_data>,
  "error": null or <error_detail>,
  "meta": {
    "request_id": "...",
    "trace_id": "...",
    "timestamp": "..."
  }
}

This middleware allows routes to return plain data/dicts,
and automatically wraps them in the standardized format.
"""

import json
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from app.modules.common.utils.response import (
    get_request_id,
    get_trace_id,
    is_api_response_like,
    is_standardized_response,
    normalize_response_payload,
)


class ResponseWrappingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically wraps all responses in standardized format.

    Features:
    - Intercepts successful responses (2xx status codes)
    - Checks if response already has standardized format
    - If not, wraps in ApiResponse format
    - Automatically adds meta with request_id, trace_id, timestamp
    - Preserves error responses (already standardized by error handlers)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        """Process request and wrap response"""
        response = await call_next(request)

        # Do not wrap OpenAPI or Swagger UI routes
        if request.url.path in ["/openapi.json", "/openapi.yaml", "/docs", "/redoc"]:
            return response

        # Get request tracking info
        request_id = get_request_id()
        trace_id = get_trace_id()

        if hasattr(request.state, "request_id"):
            request_id = request.state.request_id
        if hasattr(request.state, "trace_id"):
            trace_id = request.state.trace_id

        # Don't wrap streaming responses or non-JSON responses
        if isinstance(response, StreamingResponse):
            return response
        if not self._is_json_response(response):
            return response

        # Get status code
        status_code = response.status_code

        # Only wrap successful responses (2xx)
        # Error responses are already standardized by error handlers
        if not (200 <= status_code < 300):
            return response

        # Try to read response body
        try:
            body = b""
            if hasattr(response, "body_iterator"):
                async for chunk in response.body_iterator:
                    body += chunk
            elif hasattr(response, "body"):
                body = response.body
            else:
                # Can't read body, return as-is
                return response
        except Exception:
            # If can't read body, return as-is
            return response

        # Parse JSON body
        try:
            data = json.loads(body.decode("utf-8")) if body else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            # If not valid JSON, return as-is
            return response

        # Prepare headers (exclude Content-Length as it will be recalculated)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}

        # Check if already in standardized format
        if is_standardized_response(data):
            # Already standardized, return as-is
            return JSONResponse(
                status_code=status_code,
                content=data,
                headers=headers,
            )

        # Check if response is API-like and already contains success/data
        if is_api_response_like(data):
            normalized_response = normalize_response_payload(data, status_code, request_id, trace_id)
            return JSONResponse(
                status_code=status_code,
                content=normalized_response,
                headers=headers,
            )

        # Check if response is PaginatedResponse format
        if self._is_paginated_format(data):
            # Has pagination, keep as-is (already from paginated_response builder)
            return JSONResponse(
                status_code=status_code,
                content=data,
                headers=headers,
            )

        # Wrap in standardized format
        wrapped_response = {
            "status": status_code,
            "success": True,
            "message": None,
            "data": data,
            "error": None,
            "meta": self._create_meta_dict(request_id, trace_id),
        }

        return JSONResponse(
            status_code=status_code,
            content=wrapped_response,
            headers=headers,
        )

    @staticmethod
    def _is_json_response(response) -> bool:
        """Check if response is JSON"""
        content_type = response.headers.get("content-type", "")
        return "application/json" in content_type

    @staticmethod
    def _is_standardized_format(data) -> bool:
        """Check if response already has standardized format"""
        if not isinstance(data, dict):
            return False

        # Must have: status, success, data, error, meta
        required_keys = {"status", "success", "data", "error", "meta"}
        return required_keys.issubset(data.keys())

    @staticmethod
    def _is_paginated_format(data) -> bool:
        """Check if response is paginated format (from paginated_response builder)"""
        if not isinstance(data, dict):
            return False

        # Must have pagination field in addition to standard fields
        required_keys = {"status", "success", "data", "error", "meta", "pagination"}
        return required_keys.issubset(data.keys())

    @staticmethod
    def _create_meta_dict(request_id: str, trace_id: str) -> dict:
        """Create meta dict"""
        from datetime import datetime

        return {
            "request_id": request_id,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
