"""
Response building utilities for standardized API responses.

All responses must include: status, success, data, error, meta (with request_id, trace_id, timestamp)
Error responses use structured ErrorDetail with code, message, retryable, and optional details.
"""

import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, List, Optional, TypeVar

from app.modules.common.schemas.common import (
    ApiResponse,
    ErrorDetail,
    PaginatedResponse,
    PaginationMeta,
    ResponseMeta,
)
from app.modules.common.utils.error_codes import ALL_ERRORS, get_error_code_for_status

T = TypeVar("T")

# Context variables for request tracking
request_id_context: ContextVar[str] = ContextVar("request_id", default=None)
trace_id_context: ContextVar[str] = ContextVar("trace_id", default=None)


def get_request_id() -> str:
    """Get current request ID from context"""
    rid = request_id_context.get()
    return rid if rid else str(uuid.uuid4())


def get_trace_id() -> str:
    """Get current trace ID from context"""
    tid = trace_id_context.get()
    return tid if tid else str(uuid.uuid4())


def set_request_context(request_id: str, trace_id: str) -> None:
    """Set request and trace IDs in context"""
    request_id_context.set(request_id)
    trace_id_context.set(trace_id)


def create_meta(request_id: Optional[str] = None, trace_id: Optional[str] = None) -> ResponseMeta:
    """
    Create standardized response metadata with request tracking.

    Args:
        request_id: Optional request ID (auto-generated if not provided)
        trace_id: Optional trace ID (auto-generated if not provided)

    Returns:
        ResponseMeta with request_id, trace_id, and UTC timestamp
    """
    return ResponseMeta(
        request_id=request_id or get_request_id(),
        trace_id=trace_id or get_trace_id(),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


def is_standardized_response(data: Any) -> bool:
    """Check if a payload already contains the full API response shape."""
    if not isinstance(data, dict):
        return False

    required_keys = {"status", "success", "data", "error", "meta"}
    return required_keys.issubset(data.keys())


def is_api_response_like(data: Any) -> bool:
    """Check if a payload already has an API-like response shape."""
    if not isinstance(data, dict):
        return False

    return "success" in data and "data" in data


def normalize_response_payload(
    payload: dict,
    status_code: int,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> dict:
    """Normalize API-like payloads into the full standardized response shape."""
    meta = payload.get("meta")
    if meta is None:
        meta = create_meta(request_id, trace_id).model_dump()

    return {
        "status": payload.get("status", status_code),
        "success": payload.get("success", False),
        "message": payload.get("message"),
        "data": payload.get("data"),
        "error": payload.get("error", None),
        "meta": meta,
    }


def success_response(
    data: Optional[T] = None,
    status_code: int = 200,
    message: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ApiResponse[T]:
    """
    Create a successful API response.

    Args:
        data: Response data payload
        status_code: HTTP status code (default 200)
        message: Optional human-readable message
        request_id: Optional custom request ID
        trace_id: Optional custom trace ID

    Returns:
        ApiResponse with success=true, status, message, data, error=null, meta

    Example:
        return success_response({"user_id": 123, "name": "John"})
    """
    return ApiResponse(
        status=status_code,
        success=True,
        message=message,
        data=data,
        error=None,
        meta=create_meta(request_id, trace_id),
    )


def error_response(
    status_code: int,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    retryable: Optional[bool] = None,
    details: Optional[dict] = None,
    data: Optional[Any] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ApiResponse:
    """
    Create an error API response with structured error details.

    Response format:
    {
        "status": 400,
        "success": false,
        "data": null,
        "error": {
            "code": "VAL_INVALID_EMAIL",
            "message": "Invalid email format",
            "retryable": false,
            "details": {"field": "email"}
        },
        "meta": {...}
    }

    Args:
        status_code: HTTP status code
        error_code: Error code from error_codes registry (auto-detected if not provided)
        error_message: Error message (auto-detected from error_code if not provided)
        retryable: Whether request can be retried (auto-detected from error_code if not provided)
        details: Optional detailed error information
        data: Optional error context data
        request_id: Optional custom request ID
        trace_id: Optional custom trace ID

    Returns:
        ApiResponse with success=false, status, error detail, meta

    Example:
        return error_response(
            status_code=400,
            error_code="VAL_INVALID_EMAIL",
            error_message="Invalid email format provided",
            retryable=False,
            details={"field": "email", "provided": "invalid@"}
        )
    """
    # Auto-detect error code, message, and retryable from error code registry if not provided
    if error_code and error_code in ALL_ERRORS:
        try:
            registry_status, registry_msg, registry_retryable = ALL_ERRORS[error_code]
            # Use provided values or fall back to registry
            if error_message is None:
                error_message = registry_msg
            if retryable is None:
                retryable = registry_retryable
        except (KeyError, TypeError):
            pass

    # If still missing, use default for status code
    if error_code is None or error_message is None or retryable is None:
        detected_code, detected_msg, detected_retryable = get_error_code_for_status(status_code)
        error_code = error_code or detected_code
        error_message = error_message or detected_msg
        retryable = retryable if retryable is not None else detected_retryable

    error_detail = ErrorDetail(
        code=error_code,
        message=error_message,
        retryable=retryable,
        details=details,
    )

    return ApiResponse(
        status=status_code,
        success=False,
        data=data,
        error=error_detail,
        meta=create_meta(request_id, trace_id),
    )


def paginated_response(
    data: List[T],
    page: int,
    limit: int,
    total: int,
    status_code: int = 200,
    message: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> PaginatedResponse[T]:
    """
    Create a paginated API response.

    Args:
        data: List of items for current page
        page: Current page number (1-indexed)
        limit: Items per page
        total: Total number of items
        status_code: HTTP status code (default 200)
        message: Optional human-readable message
        request_id: Optional custom request ID
        trace_id: Optional custom trace ID

    Returns:
        PaginatedResponse with success=true, message, data, pagination meta, response meta

    Example:
        items = [user1, user2, user3]
        return paginated_response(items, page=1, limit=10, total=50)
    """
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    pagination_meta = PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    return PaginatedResponse(
        status=status_code,
        success=True,
        data=data,
        error=None,
        pagination=pagination_meta,
        meta=create_meta(request_id, trace_id),
    )
