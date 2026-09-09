"""Message constants for API responses."""


class MessageConstants:
    """Centralized registry of all message constants organized by category."""

    INVALID_CREDENTIALS = "Invalid credentials provided"
    LOGIN_SUCCESS = "Login successful"
    OPERATION_SUCCESSFUL = "Operation successful"
    USER_AVATAR_UPLOADED_SUCCESS = "User avatar uploaded successfully"
    USER_CREATED_SUCCESS = "User created successfully"
    USER_DELETED_SUCCESS = "User deleted successfully"
    USER_RETRIEVED_SUCCESS = "User retrieved successfully"
    USER_UPDATED_SUCCESS = "User updated successfully"
    VERSION_CREATED_SUCCESS = "Version created successfully"
    VERSION_RETRIEVED_SUCCESS = "Version retrieved successfully"


class MessageDescriptions:
    """Human-readable descriptions for each message constant."""

    AUTH_EMAIL_NOT_FOUND = "Unable to retrieve email from authentication provider"
    AUTH_FAILED = "Authentication failed"
    INTERNAL_SERVER_ERROR = "Internal server error"
    RESOURCE_ALREADY_EXISTS = "Resource already exists"
    USER_NOT_FOUND = "User not found"
