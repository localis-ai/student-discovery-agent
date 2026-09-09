"""
HTTP Client Utilities with Timeout Handling

Provides utilities for making HTTP calls with proper timeout configuration,
retry logic, and timeout budget management.
"""

import asyncio
import logging
from typing import Any, Optional

import aiohttp
import httpx
from aiohttp import ClientSession

from app.modules.common.config.timeout_config import (
    TimeoutBudget,
    TimeoutConfig,
    get_timeout_for_call,
)
from app.modules.common.utils.timeout_utils import (
    TimeoutException,
    with_timeout,
)

logger = logging.getLogger(__name__)


class HTTPClientWithTimeout:
    """
    HTTP client wrapper with timeout handling and retry logic.

    Example:
        client = HTTPClientWithTimeout()
        response = await client.get(
            "https://api.example.com/data",
            timeout_ms=1000,
            retries=2
        )
    """

    def __init__(self, timeout_config: Optional[dict] = None):
        """
        Initialize HTTP client.

        Args:
            timeout_config: Optional dict with timeout configuration
        """
        self.config = timeout_config or {}
        self.session: Optional[ClientSession] = None

    async def __aenter__(self):
        """Context manager entry"""
        timeout = aiohttp.ClientTimeout(total=TimeoutConfig.DEFAULT_TIMEOUT_MS / 1000)
        self.session = ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()

    async def get(
        self,
        url: str,
        timeout_ms: int = None,
        retries: int = 0,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make GET request with timeout handling.

        Args:
            url: URL to request
            timeout_ms: Timeout in milliseconds
            retries: Number of retries on timeout
            **kwargs: Additional arguments for aiohttp

        Returns:
            Response object

        Raises:
            TimeoutException: If request times out after all retries
        """
        if timeout_ms is None:
            timeout_ms = get_timeout_for_call("get")

        budget = TimeoutBudget(timeout_ms, "GET")

        for attempt in range(retries + 1):
            try:
                start = asyncio.get_event_loop().time()
                if self.session:
                    async with self.session.get(url, **kwargs) as resp:
                        return resp
                else:
                    async with httpx.AsyncClient() as client:
                        return await with_timeout(
                            client.get(url, **kwargs),
                            budget.get_remaining_ms(),
                            f"GET {url}",
                        )
            except TimeoutException:
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                budget.add_elapsed(int(elapsed))

                if attempt >= retries or budget.is_expired():
                    raise TimeoutException(
                        timeout_ms=timeout_ms,
                        message=f"GET {url} timed out after {timeout_ms}ms (attempt {attempt + 1}/{retries + 1})",
                    )

                # Calculate retry delay
                backoff_ms = budget.calculate_retry_delay_ms(attempt)
                if backoff_ms == 0:
                    raise TimeoutException(
                        timeout_ms=timeout_ms,
                        message=f"GET {url} timeout budget exceeded",
                    )

                logger.warning(
                    f"GET request timeout, retrying in {backoff_ms}ms",
                    extra={
                        "url": url,
                        "attempt": attempt + 1,
                        "backoff_ms": backoff_ms,
                    },
                )

                await asyncio.sleep(backoff_ms / 1000)

    async def post(
        self,
        url: str,
        timeout_ms: int = None,
        retries: int = 0,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make POST request with timeout handling.

        Args:
            url: URL to request
            timeout_ms: Timeout in milliseconds
            retries: Number of retries on timeout
            **kwargs: Additional arguments for aiohttp

        Returns:
            Response object

        Raises:
            TimeoutException: If request times out after all retries
        """
        if timeout_ms is None:
            timeout_ms = get_timeout_for_call("post")

        budget = TimeoutBudget(timeout_ms, "POST")

        for attempt in range(retries + 1):
            try:
                start = asyncio.get_event_loop().time()
                if self.session:
                    async with self.session.post(url, **kwargs) as resp:
                        return resp
                else:
                    async with httpx.AsyncClient() as client:
                        return await with_timeout(
                            client.post(url, **kwargs),
                            budget.get_remaining_ms(),
                            f"POST {url}",
                        )
            except TimeoutException:
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                budget.add_elapsed(int(elapsed))

                if attempt >= retries or budget.is_expired():
                    raise TimeoutException(
                        timeout_ms=timeout_ms,
                        message=f"POST {url} timed out after {timeout_ms}ms (attempt {attempt + 1}/{retries + 1})",
                    )

                # Calculate retry delay
                backoff_ms = budget.calculate_retry_delay_ms(attempt)
                if backoff_ms == 0:
                    raise TimeoutException(
                        timeout_ms=timeout_ms,
                        message=f"POST {url} timeout budget exceeded",
                    )

                logger.warning(
                    f"POST request timeout, retrying in {backoff_ms}ms",
                    extra={
                        "url": url,
                        "attempt": attempt + 1,
                        "backoff_ms": backoff_ms,
                    },
                )

                await asyncio.sleep(backoff_ms / 1000)

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()


class TimeoutBudgetTracker:
    """
    Track timeout budget across multiple internal service calls.

    Example:
        tracker = TimeoutBudgetTracker(total_ms=5000)

        # Call service A
        async with tracker.track("service_a", 500):
            await call_service_a()  # Must complete in 500ms

        # Call service B with remaining budget
        async with tracker.track("service_b"):
            await call_service_b()  # Must complete in remaining time
    """

    def __init__(self, total_ms: int = None):
        """
        Initialize budget tracker.

        Args:
            total_ms: Total timeout budget for all calls
        """
        self.total_ms = total_ms or TimeoutConfig.DEFAULT_TIMEOUT_MS
        self.budget = TimeoutBudget(self.total_ms)
        self.calls: dict[str, dict] = {}

    def get_remaining_ms(self) -> int:
        """Get remaining timeout budget"""
        return self.budget.get_remaining_ms()

    def is_expired(self) -> bool:
        """Check if timeout budget is exceeded"""
        return self.budget.is_expired()

    async def track(
        self,
        call_name: str,
        timeout_ms: int = None,
    ):
        """
        Context manager to track a call within timeout budget.

        Args:
            call_name: Name of the call
            timeout_ms: Timeout for this call (uses remaining budget if not specified)

        Yields:
            Timeout value in milliseconds

        Raises:
            TimeoutException: If timeout budget exceeded
        """
        if self.is_expired():
            raise TimeoutException(
                timeout_ms=self.total_ms,
                message=f"Timeout budget exhausted (total: {self.total_ms}ms)",
            )

        # Use specified timeout or remaining budget
        actual_timeout_ms = timeout_ms or self.get_remaining_ms()

        if actual_timeout_ms <= 0:
            raise TimeoutException(
                timeout_ms=self.total_ms,
                message=f"No remaining timeout budget (total: {self.total_ms}ms)",
            )

        start = asyncio.get_event_loop().time()
        try:
            yield actual_timeout_ms
        finally:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            self.budget.add_elapsed(int(elapsed))
            self.calls[call_name] = {
                "timeout_ms": actual_timeout_ms,
                "elapsed_ms": int(elapsed),
                "exceeded": elapsed > actual_timeout_ms,
            }

            logger.info(
                f"Call '{call_name}' completed",
                extra={
                    "call_name": call_name,
                    "timeout_ms": actual_timeout_ms,
                    "elapsed_ms": int(elapsed),
                    "remaining_ms": self.get_remaining_ms(),
                },
            )

    def get_summary(self) -> dict:
        """Get summary of all tracked calls"""
        return {
            "total_timeout_ms": self.total_ms,
            "total_elapsed_ms": self.budget.elapsed_ms,
            "remaining_ms": self.get_remaining_ms(),
            "is_expired": self.is_expired(),
            "calls": self.calls,
        }
