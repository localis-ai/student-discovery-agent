import uuid
from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from fastapi.params import Query
from pydantic import BaseModel, ConfigDict, Field
from pytz import timezone

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses"""

    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ResponseMeta(BaseModel):
    """Standard response metadata with request tracking"""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request identifier")
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Trace ID for distributed tracing")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone("Asia/Ho_Chi_Minh")).isoformat() + "Z", description="Response timestamp in ISO8601 UTC format")

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    """Structured error response with code, message, and metadata"""

    code: str = Field(description="Error code (e.g., SYS_503, USR_404)")
    message: str = Field(description="Human-readable error message")
    retryable: bool = Field(default=False, description="Whether the operation can be retried")
    details: Optional[dict] = Field(default=None, description="Optional detailed error information")

    model_config = ConfigDict(from_attributes=True)


class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper for all endpoints.

    Format (Success):
    {
        "status": 200,
        "success": true,
        "data": <T>,
        "error": null,
        "meta": {...}
    }

    Format (Error):
    {
        "status": 400,
        "success": false,
        "data": null,
        "error": {"code": "USR_400", "message": "...", "retryable": false},
        "meta": {...}
    }
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")  # Ignore extra fields for backwards compatibility

    status: int = Field(default=200, description="HTTP status code")
    success: bool = Field(default=True, description="Request success status")
    message: Optional[str] = Field(default=None, description="Human-readable message")
    data: Optional[T] = Field(default=None, description="Response data")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details if failed, null if success")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata with request tracking")


class PaginatedResponse(ApiResponse[List[T]], Generic[T]):
    """Paginated API response with pagination metadata"""

    pagination: Optional[PaginationMeta] = Field(default=None, description="Pagination information")


def create_pagination_meta(page: int, limit: int, total: int) -> PaginationMeta:
    """Create pagination metadata"""
    total_pages = (total + limit - 1) // limit  # Ceiling division
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


class PaginationSortSearchSchema(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=100)
    sort_key: Optional[str] = Field(default=None)
    sort_dir: Optional[str] = Field(default=None)
    search: Optional[str] = Field(default=None)

    model_config = ConfigDict(from_attributes=True)


def pagination_params_dep(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    sort_key: Optional[str] = Query(None, description="Field to sort by"),
    sort_dir: Optional[str] = Query(None, description="Sort direction: asc or desc"),
    search: Optional[str] = Query(None, description="Search term to filter results"),
) -> PaginationSortSearchSchema:
    return PaginationSortSearchSchema(skip=skip, limit=limit, sort_key=sort_key, sort_dir=sort_dir, search=search)
