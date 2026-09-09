"""
Error code mapping and utilities for standardized error responses.

Error Code Format: PREFIX_CODE
Prefixes:
  - AUTH_ : Authentication (401)
  - AUTHZ_ : Authorization (403)
  - RES_ : Resource not found (404)
  - VAL_ : Validation (400/422)
  - REQ_ : Business logic (200/422)
  - DB_ : Database (500)
  - EXT_ : External service (502/503)
  - SYS_ : System error (500/503)
"""

# ============================================================================
# Error Code Mappings: (HTTP_STATUS, ERROR_CODE, MESSAGE, RETRYABLE)
# ============================================================================

# Authentication Errors (AUTH_*) - 401 Unauthorized
AUTH_ERRORS = {
    "AUTH_MISSING_TOKEN": (401, "Missing authentication token", False),
    "AUTH_INVALID_TOKEN": (401, "Invalid or malformed token", False),
    "AUTH_EXPIRED_TOKEN": (401, "Token has expired", True),
    "AUTH_INVALID_CREDENTIALS": (401, "Invalid credentials provided", False),
    "AUTH_SESSION_EXPIRED": (401, "User session has expired", True),
    "AUTH_ACCOUNT_NOT_ACTIVATED": (401, "Account is not activated", False),
    "AUTH_ACCOUNT_SUSPENDED": (401, "Account has been suspended", False),
}

# Authorization Errors (AUTHZ_*) - 403 Forbidden
AUTHZ_ERRORS = {
    "AUTHZ_INSUFFICIENT_PERMISSION": (403, "Insufficient permissions for this operation", False),
    "AUTHZ_ADMIN_REQUIRED": (403, "Admin access required", False),
    "AUTHZ_OWNER_REQUIRED": (403, "Owner access required", False),
    "AUTHZ_RESOURCE_ACCESS_DENIED": (403, "Access to resource denied", False),
    "AUTHZ_PROJECT_ACCESS_DENIED": (403, "Access to project denied", False),
    "AUTHZ_MEETING_ACCESS_DENIED": (403, "Access to meeting denied", False),
}

# Resource Not Found Errors (RES_*) - 404 Not Found
RES_ERRORS = {
    "RES_USER_NOT_FOUND": (404, "User not found", False),
    "RES_MEETING_NOT_FOUND": (404, "Meeting not found", False),
    "RES_PROJECT_NOT_FOUND": (404, "Project not found", False),
    "RES_FILE_NOT_FOUND": (404, "File not found", False),
    "RES_TRANSCRIPT_NOT_FOUND": (404, "Transcript not found", False),
    "RES_TASK_NOT_FOUND": (404, "Task not found", False),
    "RES_CONVERSATION_NOT_FOUND": (404, "Conversation not found", False),
    "RES_MESSAGE_NOT_FOUND": (404, "Message not found", False),
    "RES_NOTIFICATION_NOT_FOUND": (404, "Notification not found", False),
    "RES_ROLE_REQUEST_NOT_FOUND": (404, "Role request not found", False),
}

# Validation Errors (VAL_*) - 400/422
VAL_ERRORS = {
    # Email validation
    "VAL_INVALID_EMAIL": (400, "Invalid email format", False),
    "VAL_EMAIL_REQUIRED": (400, "Email is required", False),
    "VAL_EMAIL_TOO_LONG": (400, "Email exceeds maximum length", False),
    "VAL_DUPLICATE_EMAIL": (422, "Email is already registered", False),
    # Password validation
    "VAL_PASSWORD_REQUIRED": (400, "Password is required", False),
    "VAL_PASSWORD_TOO_SHORT": (400, "Password must be at least 8 characters", False),
    "VAL_PASSWORD_TOO_LONG": (400, "Password exceeds maximum length", False),
    "VAL_PASSWORD_NO_UPPERCASE": (400, "Password must contain uppercase letter", False),
    "VAL_PASSWORD_NO_LOWERCASE": (400, "Password must contain lowercase letter", False),
    "VAL_PASSWORD_NO_DIGIT": (400, "Password must contain digit", False),
    "VAL_PASSWORD_NO_SPECIAL": (400, "Password must contain special character", False),
    "VAL_PASSWORD_MISMATCH": (400, "Passwords do not match", False),
    "VAL_WRONG_PASSWORD": (422, "Current password is incorrect", False),
    # User validation
    "VAL_INVALID_USER_ID": (400, "Invalid user ID format", False),
    "VAL_NAME_REQUIRED": (400, "Name is required", False),
    "VAL_NAME_TOO_LONG": (400, "Name exceeds maximum length", False),
    # Project validation
    "VAL_PROJECT_NAME_REQUIRED": (400, "Project name is required", False),
    "VAL_PROJECT_NAME_TOO_LONG": (400, "Project name exceeds 255 characters", False),
    "VAL_PROJECT_DESC_TOO_LONG": (400, "Project description exceeds 5000 characters", False),
    "VAL_INVALID_PROJECT_ID": (400, "Invalid project ID format", False),
    # Meeting validation
    "VAL_MEETING_TITLE_REQUIRED": (400, "Meeting title is required", False),
    "VAL_INVALID_MEETING_TYPE": (400, "Invalid meeting type", False),
    "VAL_START_AFTER_END": (400, "Start time must be before end time", False),
    "VAL_PAST_DATETIME": (400, "Date/time cannot be in the past", False),
    "VAL_INVALID_MEETING_ID": (400, "Invalid meeting ID format", False),
    # File validation
    "VAL_FILE_TOO_LARGE": (400, "File size exceeds 50MB limit", False),
    "VAL_UNSUPPORTED_FILE_TYPE": (400, "File type not supported", False),
    "VAL_EMPTY_FILE": (400, "File is empty", False),
    "VAL_INVALID_FILE_ID": (400, "Invalid file ID format", False),
    # Content validation
    "VAL_MESSAGE_EMPTY": (400, "Message content cannot be empty", False),
    "VAL_MESSAGE_TOO_LONG": (400, "Message exceeds maximum length", False),
    "VAL_ARRAY_EMPTY": (400, "Array cannot be empty", False),
    "VAL_INVALID_ARRAY_ITEM": (400, "Array contains invalid item", False),
}

# Business Logic Errors (REQ_*) - 200/422
REQ_ERRORS = {
    # Project management
    "REQ_PROJECT_MEMBER_EXISTS": (200, "User is already a member of this project", False),
    "REQ_PROJECT_NOT_MEMBER": (422, "User is not a member of this project", False),
    "REQ_PROJECT_NO_ADMINS": (422, "Cannot remove all admins from project", False),
    "REQ_LAST_ADMIN_CANNOT_LEAVE": (422, "Last admin cannot leave project", False),
    "REQ_CANNOT_REMOVE_LAST_ADMIN": (422, "Cannot remove the last admin", False),
    # Meeting management
    "REQ_MEETING_WRONG_PROJECT": (422, "Meeting belongs to different project", False),
    "REQ_MEETING_IN_PAST": (422, "Cannot modify past meeting", False),
    "REQ_MEETING_NO_AUDIO": (422, "Meeting has no audio for transcription", False),
    "REQ_MEETING_ALREADY_TRANSCRIBING": (200, "Meeting transcription already in progress", True),
    # Chat & messaging
    "REQ_CONV_USER_EXISTS": (200, "User already in conversation", False),
    "REQ_CONV_MAX_PARTICIPANTS": (422, "Conversation has max participants", False),
    "REQ_DUPLICATE_ROLE_REQUEST": (200, "User already has pending role request", False),
    # File operations
    "REQ_FILE_NOT_ACCESSIBLE": (200, "File not accessible", False),
    "REQ_FILE_ALREADY_EXISTS": (200, "File already exists in target location", False),
}

# Database Errors (DB_*) - 500
DB_ERRORS = {
    "DB_CONNECTION_ERROR": (500, "Database connection failed", True),
    "DB_QUERY_ERROR": (500, "Database query failed", False),
    "DB_TRANSACTION_ERROR": (500, "Database transaction failed", True),
}

# External Service Errors (EXT_*) - 502/503
EXT_ERRORS = {
    "EXT_TRANSCRIPTION_FAILED": (503, "Audio transcription failed", True),
    "EXT_AI_SERVICE_ERROR": (503, "AI service unavailable", True),
    "EXT_STORAGE_ERROR": (503, "File storage service error", True),
    "EXT_SEARCH_SERVICE_ERROR": (503, "Search service unavailable", True),
    "EXT_EMAIL_SEND_FAILURE": (503, "Failed to send email", True),
    "EXT_WEBHOOK_DELIVERY_FAILED": (503, "Webhook delivery failed", True),
    "EXT_UPSTREAM_ERROR": (502, "Upstream service error", True),
}

# System Errors (SYS_*) - 500/503
SYS_ERRORS = {
    "SYS_INTERNAL_ERROR": (500, "Internal server error", True),
    "SYS_SERVICE_UNAVAILABLE": (503, "Service temporarily unavailable", True),
    "SYS_REQUEST_TIMEOUT": (504, "Request timeout", True),
    "SYS_RATE_LIMIT_EXCEEDED": (429, "Rate limit exceeded", True),
    "SYS_INVALID_CONFIG": (500, "Invalid service configuration", False),
}

# Combined error registry for lookup
ALL_ERRORS = {
    **AUTH_ERRORS,
    **AUTHZ_ERRORS,
    **RES_ERRORS,
    **VAL_ERRORS,
    **REQ_ERRORS,
    **DB_ERRORS,
    **EXT_ERRORS,
    **SYS_ERRORS,
}


def get_error_info(error_code: str) -> tuple[int, str, bool]:
    """
    Get HTTP status, message, and retryable flag for error code.

    Args:
        error_code: Error code (e.g., "VAL_INVALID_EMAIL")

    Returns:
        Tuple of (status_code, message, retryable)

    Raises:
        ValueError: If error code not found in registry
    """
    if error_code not in ALL_ERRORS:
        raise ValueError(f"Unknown error code: {error_code}")

    return ALL_ERRORS[error_code]


def get_error_code_for_status(status_code: int) -> tuple[str, str, bool]:
    """
    Get default error code, message, and retryable flag for HTTP status.

    Args:
        status_code: HTTP status code

    Returns:
        Tuple of (error_code, message, retryable)
    """
    status_code_defaults = {
        400: ("VAL_INVALID_REQUEST", "Invalid request", False),
        401: ("AUTH_INVALID_TOKEN", "Unauthorized", False),
        403: ("AUTHZ_INSUFFICIENT_PERMISSION", "Forbidden", False),
        404: ("RES_NOT_FOUND", "Not found", False),
        422: ("VAL_UNPROCESSABLE", "Unprocessable entity", False),
        429: ("SYS_RATE_LIMIT_EXCEEDED", "Rate limit exceeded", True),
        500: ("SYS_INTERNAL_ERROR", "Internal server error", True),
        502: ("EXT_UPSTREAM_ERROR", "Bad gateway", True),
        503: ("EXT_TRANSCRIPTION_FAILED", "Service unavailable", True),
        504: ("SYS_REQUEST_TIMEOUT", "Gateway timeout", True),
    }

    return status_code_defaults.get(status_code, ("SYS_INTERNAL_ERROR", "Internal server error", True))


def get_error_code_details(error_code: str) -> dict:
    """
    Get full error details as dictionary for specific error code.

    Args:
        error_code: Error code (e.g., "VAL_INVALID_EMAIL")

    Returns:
        Dictionary with keys: code, status, message, retryable

    Raises:
        ValueError: If error code not found in registry
    """
    if error_code not in ALL_ERRORS:
        raise ValueError(f"Unknown error code: {error_code}")

    status_code, message, retryable = ALL_ERRORS[error_code]
    return {
        "code": error_code,
        "status": status_code,
        "message": message,
        "retryable": retryable,
    }


# Common error code constants for easy import
COMMON_ERRORS = {
    "INVALID_EMAIL": "VAL_INVALID_EMAIL",
    "DUPLICATE_EMAIL": "VAL_DUPLICATE_EMAIL",
    "INVALID_PASSWORD": "VAL_PASSWORD_TOO_SHORT",
    "UNAUTHORIZED": "AUTH_INVALID_TOKEN",
    "FORBIDDEN": "AUTHZ_INSUFFICIENT_PERMISSION",
    "NOT_FOUND": "RES_NOT_FOUND",
    "USER_NOT_FOUND": "RES_USER_NOT_FOUND",
    "PROJECT_NOT_FOUND": "RES_PROJECT_NOT_FOUND",
    "MEETING_NOT_FOUND": "RES_MEETING_NOT_FOUND",
    "INTERNAL_ERROR": "SYS_INTERNAL_ERROR",
    "DATABASE_ERROR": "DB_CONNECTION_ERROR",
    "SERVICE_UNAVAILABLE": "EXT_UPSTREAM_ERROR",
}
