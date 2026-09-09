"""
Timeout Utilities for Backend API

Provides timeout decorators, exception handling, and timeout utilities.
"""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from app.exception_handlers.http_exception import AppException
from app.modules.common.utils.error_codes import get_error_code_details

# Type variables for decorators
F = TypeVar("F", bound=Callable[..., Any])


class TimeoutException(AppException):
    """Exception raised when a call times out"""

    def __init__(self, timeout_ms: int, message: Optional[str] = None):
        """
        Initialize timeout exception.

        Args:
            timeout_ms: Timeout duration in milliseconds
            message: Optional custom message
        """
        self.timeout_ms = timeout_ms
        default_message = f"The request timed out after {timeout_ms}ms."

        super().__init__(
            status_code=408,  # Request Timeout
            error_code="SYS_REQUEST_TIMEOUT",
            message=message or default_message,
            retryable=True,
            details={
                "timeout_ms": timeout_ms,
                "configured_timeout": timeout_ms,
            },
        )


def timeout_async(timeout_ms: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to add timeout to async functions.

    Args:
        timeout_ms: Timeout duration in milliseconds

    Returns:
        Decorated function with timeout

    Example:
        @timeout_async(1000)
        async def fetch_data():
            await asyncio.sleep(2)  # Will timeout
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                timeout_seconds = timeout_ms / 1000
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError as e:
                raise TimeoutException(timeout_ms=timeout_ms, message=f"Async function '{func.__name__}' timed out after {timeout_ms}ms.") from e

        return async_wrapper

    return decorator


def timeout_sync(timeout_ms: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to add timeout to sync functions (using signal on Unix/Linux).

    Note: This only works on Unix/Linux systems. On Windows or for async code,
    use timeout_async() or manual timeout handling.

    Args:
        timeout_ms: Timeout duration in milliseconds

    Returns:
        Decorated function with timeout

    Example:
        @timeout_sync(1000)
        def fetch_data():
            time.sleep(2)  # Will timeout (Unix/Linux only)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import signal
            import sys

            # signal.alarm() only works on Unix/Linux
            if sys.platform not in ["linux", "linux2", "darwin"]:
                # Fallback: just call the function without timeout
                return func(*args, **kwargs)

            def timeout_handler(signum: int, frame: Any) -> None:
                raise TimeoutException(timeout_ms=timeout_ms, message=f"Sync function '{func.__name__}' timed out after {timeout_ms}ms.")

            # Set signal handler and alarm
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_ms / 1000) + 1)  # Round up seconds

            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancel alarm
                return result
            except TimeoutException:
                raise
            finally:
                signal.alarm(0)  # Ensure alarm is cancelled

        return wrapper

    return decorator


class TimedOperation:
    """Context manager for timing operations and enforcing timeouts"""

    def __init__(self, timeout_ms: int, operation_name: str = "operation"):
        """
        Initialize timed operation.

        Args:
            timeout_ms: Timeout duration in milliseconds
            operation_name: Name of the operation (for error messages)
        """
        self.timeout_ms = timeout_ms
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
        self.elapsed_ms: float = 0

    def __enter__(self) -> "TimedOperation":
        """Enter context manager"""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager"""
        if self.start_time:
            self.elapsed_ms = (time.time() - self.start_time) * 1000

            if self.elapsed_ms > self.timeout_ms:
                raise TimeoutException(timeout_ms=self.timeout_ms, message=f"{self.operation_name} exceeded timeout of {self.timeout_ms}ms (took {self.elapsed_ms:.0f}ms).")

    def get_elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        if self.start_time:
            return (time.time() - self.start_time) * 1000
        return 0

    def get_remaining_ms(self) -> float:
        """Get remaining time in milliseconds"""
        return max(0, self.timeout_ms - self.get_elapsed_ms())

    def is_expired(self) -> bool:
        """Check if timeout is exceeded"""
        return self.get_elapsed_ms() > self.timeout_ms


async def with_timeout(coro: Any, timeout_ms: int, operation_name: str = "operation") -> Any:
    """
    Execute coroutine with timeout.

    Args:
        coro: Coroutine to execute
        timeout_ms: Timeout in milliseconds
        operation_name: Name of the operation (for error messages)

    Returns:
        Result of coroutine

    Raises:
        TimeoutException: If coroutine exceeds timeout

    Example:
        result = await with_timeout(fetch_data(), 1000, "fetch data")
    """
    try:
        timeout_seconds = timeout_ms / 1000
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError as e:
        raise TimeoutException(timeout_ms=timeout_ms, message=f"{operation_name} timed out after {timeout_ms}ms.") from e


def get_timeout_error_response(timeout_ms: int, operation_name: str = "request") -> dict:
    """
    Get standardized timeout error response.

    Args:
        timeout_ms: Timeout duration in milliseconds
        operation_name: Name of the operation that timed out

    Returns:
        Standardized error response dict with success=false

    Example:
        error_response = get_timeout_error_response(2000, "fetch user data")
        # Returns: {
        #   "success": false,
        #   "error": {
        #     "code": "SYS_REQUEST_TIMEOUT",
        #     "message": "...",
        #     "retryable": true
        #   },
        #   "meta": {...}
        # }
    """
    error_info = get_error_code_details("SYS_REQUEST_TIMEOUT")
    return {
        "success": False,
        "error": {
            "code": "SYS_REQUEST_TIMEOUT",
            "message": error_info.get("message", f"{operation_name} timed out after {timeout_ms}ms."),
            "retryable": error_info.get("retryable", True),
            "details": {
                "timeout_ms": timeout_ms,
                "operation": operation_name,
            },
        },
    }
