"""
Async rate limiter for LLM API calls.

Implements token bucket algorithm with per-provider rate limits
and retry logic with exponential backoff.
"""

import asyncio
import time
import logging
from typing import Callable, TypeVar, Optional, Dict, Any
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting per provider."""
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    max_concurrent: int = 10
    batch_delay_seconds: float = 0.1
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_exponential_base: float = 2.0


# Default configurations per provider
DEFAULT_RATE_LIMITS: Dict[str, RateLimitConfig] = {
    "claude": RateLimitConfig(
        requests_per_minute=50,
        tokens_per_minute=100000,
        max_concurrent=5,
    ),
    "openai": RateLimitConfig(
        requests_per_minute=60,
        tokens_per_minute=150000,
        max_concurrent=10,
    ),
    "google": RateLimitConfig(
        requests_per_minute=60,
        tokens_per_minute=100000,
        max_concurrent=5,
    ),
}


class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursting up to bucket capacity, then limits to refill rate.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,  # tokens per second
    ):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire tokens from bucket.

        Waits if insufficient tokens available.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        async with self._lock:
            waited = 0.0

            while True:
                self._refill()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return waited

                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate

                # Release lock while waiting
                self._lock.release()
                try:
                    await asyncio.sleep(wait_time)
                    waited += wait_time
                finally:
                    await self._lock.acquire()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class AsyncRateLimiter:
    """
    Async rate limiter with multiple buckets and retry logic.

    Combines request rate limiting, token rate limiting, and
    concurrency limiting.
    """

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        provider: Optional[str] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
            provider: Provider name (uses default config if not specified)
        """
        if config is None:
            config = DEFAULT_RATE_LIMITS.get(provider, RateLimitConfig())

        self.config = config

        # Request rate bucket (requests per minute -> per second)
        self._request_bucket = TokenBucket(
            capacity=config.requests_per_minute,
            refill_rate=config.requests_per_minute / 60.0,
        )

        # Token rate bucket (tokens per minute -> per second)
        self._token_bucket = TokenBucket(
            capacity=config.tokens_per_minute,
            refill_rate=config.tokens_per_minute / 60.0,
        )

        # Concurrency semaphore
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

        # Statistics
        self._stats = {
            "requests": 0,
            "tokens": 0,
            "retries": 0,
            "failures": 0,
            "total_wait_time": 0.0,
        }

    async def acquire(self, estimated_tokens: int = 1000) -> float:
        """
        Acquire rate limit permission.

        Waits for both request and token buckets.

        Args:
            estimated_tokens: Estimated tokens for this request

        Returns:
            Time waited in seconds
        """
        waited = 0.0

        # Acquire request slot
        waited += await self._request_bucket.acquire(1.0)

        # Acquire token budget
        waited += await self._token_bucket.acquire(estimated_tokens)

        self._stats["total_wait_time"] += waited
        return waited

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        estimated_tokens: int = 1000,
        **kwargs,
    ) -> T:
        """
        Execute function with rate limiting.

        Args:
            func: Async function to execute
            *args: Function arguments
            estimated_tokens: Estimated tokens for request
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        await self.acquire(estimated_tokens)

        async with self._semaphore:
            self._stats["requests"] += 1
            return await func(*args, **kwargs)

    async def execute_with_retry(
        self,
        func: Callable[..., T],
        *args,
        estimated_tokens: int = 1000,
        **kwargs,
    ) -> T:
        """
        Execute function with rate limiting and retry logic.

        Retries on rate limit errors with exponential backoff.

        Args:
            func: Async function to execute
            *args: Function arguments
            estimated_tokens: Estimated tokens for request
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        from .provider_base import RateLimitError

        last_error = None
        delay = self.config.retry_base_delay

        for attempt in range(self.config.max_retries + 1):
            try:
                return await self.execute(
                    func, *args,
                    estimated_tokens=estimated_tokens,
                    **kwargs
                )
            except RateLimitError as e:
                last_error = e
                self._stats["retries"] += 1

                if attempt < self.config.max_retries:
                    # Use retry_after hint if available
                    wait_time = e.retry_after if e.retry_after else delay
                    wait_time = min(wait_time, self.config.retry_max_delay)

                    logger.warning(
                        f"Rate limited, retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{self.config.max_retries})"
                    )

                    await asyncio.sleep(wait_time)
                    delay *= self.config.retry_exponential_base
                else:
                    logger.error(f"Rate limit retries exhausted: {e}")
                    self._stats["failures"] += 1
                    raise

            except Exception as e:
                # Don't retry non-rate-limit errors
                self._stats["failures"] += 1
                raise

        raise last_error  # Should not reach here

    def record_tokens(self, tokens_used: int):
        """Record actual token usage for statistics."""
        self._stats["tokens"] += tokens_used

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return dict(self._stats)

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "requests": 0,
            "tokens": 0,
            "retries": 0,
            "failures": 0,
            "total_wait_time": 0.0,
        }


class RateLimiterPool:
    """
    Pool of rate limiters for multiple providers.

    Manages separate rate limiters for each provider.
    """

    def __init__(self):
        self._limiters: Dict[str, AsyncRateLimiter] = {}

    def get_limiter(
        self,
        provider: str,
        config: Optional[RateLimitConfig] = None,
    ) -> AsyncRateLimiter:
        """
        Get or create rate limiter for provider.

        Args:
            provider: Provider name
            config: Optional custom configuration

        Returns:
            AsyncRateLimiter for the provider
        """
        if provider not in self._limiters:
            self._limiters[provider] = AsyncRateLimiter(
                config=config,
                provider=provider,
            )
        return self._limiters[provider]

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all providers."""
        return {
            provider: limiter.get_stats()
            for provider, limiter in self._limiters.items()
        }

    def reset_all_stats(self):
        """Reset statistics for all providers."""
        for limiter in self._limiters.values():
            limiter.reset_stats()


# Global rate limiter pool
_rate_limiter_pool = RateLimiterPool()


def get_rate_limiter(provider: str) -> AsyncRateLimiter:
    """Get rate limiter for a provider from the global pool."""
    return _rate_limiter_pool.get_limiter(provider)


def get_all_rate_limiter_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics from all rate limiters."""
    return _rate_limiter_pool.get_all_stats()
