"""
Timeout Configuration for Backend API

Defines timeout values for different types of external calls:
- GET requests: 100ms-1s
- POST/PUT requests: 300ms-2s
- Internal calls: 200ms-1s
- AI/OCR: async/queue (no timeout)
"""

from datetime import timedelta

# ============================================================================
# Timeout Configuration (in milliseconds)
# ============================================================================


class TimeoutConfig:
    """Timeout values for different types of API calls"""

    # HTTP Method Timeouts
    GET_TIMEOUT_MS = 5000  # 500ms for GET requests
    POST_TIMEOUT_MS = 12000  # 1.2s for POST requests
    PUT_TIMEOUT_MS = 12000  # 1.2s for PUT requests
    DELETE_TIMEOUT_MS = 8000  # 800ms for DELETE requests

    # Internal Service Timeouts
    INTERNAL_CALL_TIMEOUT_MS = 5000  # 500ms for inter-service calls
    DATABASE_TIMEOUT_MS = 10000  # 1s for database operations
    REDIS_TIMEOUT_MS = 3000  # 300ms for Redis operations

    # External Service Timeouts
    TRANSCRIPTION_TIMEOUT_MS = 30000000  # 30s for audio transcription (async)
    AI_SERVICE_TIMEOUT_MS = 50000  # 5s for AI services (chat/summarization)
    STORAGE_TIMEOUT_MS = 100000  # 10s for file storage operations
    SEARCH_SERVICE_TIMEOUT_MS = 20000  # 2s for search/vector db
    EMAIL_TIMEOUT_MS = 50000  # 5s for email service
    WEBHOOK_TIMEOUT_MS = 100000  # 10s for webhook delivery

    # Retry Configuration
    RETRY_ATTEMPTS = 2  # Number of retry attempts
    RETRY_BACKOFF_MS = 1000  # Base backoff between retries (exponential)

    # Default timeout for unspecified calls
    DEFAULT_TIMEOUT_MS = 10000  # 1s default


class HTTPClientTimeouts:
    """Timeout configuration for HTTP requests (used by aiohttp, httpx)"""

    def __init__(self, total_ms: int = None, connect_ms: int = None, read_ms: int = None):
        """
        Initialize HTTP timeouts.

        Args:
            total_ms: Total timeout for entire request (includes redirects)
            connect_ms: Timeout for connection establishment
            read_ms: Timeout for reading response data
        """
        self.total_ms = total_ms or TimeoutConfig.DEFAULT_TIMEOUT_MS
        self.connect_ms = connect_ms or (self.total_ms // 3)  # 1/3 of total
        self.read_ms = read_ms or (self.total_ms * 2 // 3)  # 2/3 of total

    def as_tuple(self) -> tuple:
        """Return as tuple for httpx/aiohttp (total, read, connect)"""
        return (self.total_ms / 1000, self.read_ms / 1000, self.connect_ms / 1000)

    def as_dict(self) -> dict:
        """Return as dict for requests library"""
        return {
            "total": self.total_ms / 1000,
            "read": self.read_ms / 1000,
            "connect": self.connect_ms / 1000,
        }


class DatabaseTimeouts:
    """Timeout configuration for database connections"""

    def __init__(self, connection_timeout_ms: int = None, query_timeout_ms: int = None):
        """
        Initialize database timeouts.

        Args:
            connection_timeout_ms: Timeout for connection establishment
            query_timeout_ms: Timeout for query execution
        """
        self.connection_timeout_ms = connection_timeout_ms or 500
        self.query_timeout_ms = query_timeout_ms or 1000

    def as_timedelta(self) -> timedelta:
        """Return as timedelta"""
        return timedelta(milliseconds=self.query_timeout_ms)

    def as_seconds(self) -> float:
        """Return as seconds (float)"""
        return self.query_timeout_ms / 1000


# ============================================================================
# Timeout Budget Calculator
# ============================================================================


class TimeoutBudget:
    """
    Calculate and track timeout budgets for calls with retries.

    Example:
        budget = TimeoutBudget(total_ms=2000, method="POST")
        latency_per_call_ms = 250
        backoff_per_retry_ms = 100
        max_retries = budget.calculate_max_retries(latency_per_call_ms, backoff_per_retry_ms)
    """

    def __init__(self, total_ms: int, method: str = "GET"):
        """
        Initialize timeout budget.

        Args:
            total_ms: Total timeout budget in milliseconds
            method: HTTP method (GET, POST, PUT, etc.) for default timeout
        """
        self.total_ms = total_ms
        self.method = method.upper()
        self.elapsed_ms = 0

    def get_remaining_ms(self) -> int:
        """Get remaining timeout"""
        return max(0, self.total_ms - self.elapsed_ms)

    def add_elapsed(self, elapsed_ms: int) -> None:
        """Track elapsed time"""
        self.elapsed_ms += elapsed_ms

    def is_expired(self) -> bool:
        """Check if timeout budget is exceeded"""
        return self.elapsed_ms >= self.total_ms

    def calculate_max_retries(self, latency_per_call_ms: int, backoff_per_retry_ms: int) -> int:
        """
        Calculate maximum number of retries within budget.

        Formula: retries × latency + retries × backoff ≤ total_ms
                 retries × (latency + backoff) ≤ total_ms
                 retries ≤ total_ms / (latency + backoff)

        Args:
            latency_per_call_ms: Expected latency per call
            backoff_per_retry_ms: Backoff time per retry

        Returns:
            Maximum number of retries
        """
        if latency_per_call_ms <= 0:
            return 0

        cost_per_retry_ms = latency_per_call_ms + backoff_per_retry_ms
        max_retries = self.total_ms // cost_per_retry_ms

        # Ensure at least 0 retries
        return max(0, int(max_retries))

    def calculate_retry_delay_ms(self, attempt: int, base_backoff_ms: int = 100) -> int:
        """
        Calculate retry delay with exponential backoff.

        Formula: delay = base_backoff × 2^attempt

        Args:
            attempt: Retry attempt number (0-indexed)
            base_backoff_ms: Base backoff in milliseconds

        Returns:
            Delay in milliseconds, or 0 if would exceed budget
        """
        delay_ms = base_backoff_ms * (2**attempt)

        # Ensure delay doesn't exceed remaining budget
        if self.elapsed_ms + delay_ms >= self.total_ms:
            return 0

        return delay_ms


# ============================================================================
# Timeout Presets by API Category
# ============================================================================


TIMEOUT_PRESETS = {
    "get": TimeoutConfig.GET_TIMEOUT_MS,
    "post": TimeoutConfig.POST_TIMEOUT_MS,
    "put": TimeoutConfig.PUT_TIMEOUT_MS,
    "delete": TimeoutConfig.DELETE_TIMEOUT_MS,
    "internal": TimeoutConfig.INTERNAL_CALL_TIMEOUT_MS,
    "database": TimeoutConfig.DATABASE_TIMEOUT_MS,
    "redis": TimeoutConfig.REDIS_TIMEOUT_MS,
    "transcription": TimeoutConfig.TRANSCRIPTION_TIMEOUT_MS,
    "ai": TimeoutConfig.AI_SERVICE_TIMEOUT_MS,
    "storage": TimeoutConfig.STORAGE_TIMEOUT_MS,
    "search": TimeoutConfig.SEARCH_SERVICE_TIMEOUT_MS,
    "email": TimeoutConfig.EMAIL_TIMEOUT_MS,
    "webhook": TimeoutConfig.WEBHOOK_TIMEOUT_MS,
}


def get_timeout_for_call(call_type: str) -> int:
    """
    Get timeout for specific call type.

    Args:
        call_type: Type of call (key in TIMEOUT_PRESETS)

    Returns:
        Timeout in milliseconds
    """
    return TIMEOUT_PRESETS.get(call_type.lower(), TimeoutConfig.DEFAULT_TIMEOUT_MS)
