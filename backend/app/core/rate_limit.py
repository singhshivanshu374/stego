"""
SecureStego — Redis-Based Rate Limiter

Rule 5.4: /decode is rate-limited more strictly than /encode.
Default: /encode = 20/min, /decode = 5/min per user.

When Redis is unavailable or disabled (RATE_LIMIT_ENABLED=false), the limiter
is a no-op so the app still works in local dev/testing without Redis.
"""

import logging
import time
from typing import Optional

from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory fallback when Redis is disabled (for testing)
_in_memory_store: dict[str, list[float]] = {}


async def check_rate_limit(
    user_id: int,
    endpoint: str,
    max_requests: Optional[int] = None,
    window_seconds: int = 60,
) -> None:
    """Check and enforce rate limit for a user on an endpoint.

    Uses Redis sliding window if available, otherwise falls back to
    in-memory tracking (suitable for single-process testing only).

    Args:
        user_id: The authenticated user's ID.
        endpoint: Endpoint identifier ("encode" or "decode").
        max_requests: Max requests per window. If None, uses config defaults.
        window_seconds: Sliding window size in seconds.

    Raises:
        HTTPException 429: If rate limit is exceeded.
    """
    if not settings.rate_limit_enabled:
        # Rate limiting disabled — no-op for local dev/testing
        return

    if max_requests is None:
        if endpoint == "decode":
            max_requests = settings.rate_limit_decode_per_minute
        else:
            max_requests = settings.rate_limit_encode_per_minute

    key = f"rate_limit:{user_id}:{endpoint}"
    now = time.time()
    window_start = now - window_seconds

    # Try Redis first
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        async with r.pipeline(transaction=True) as pipe:
            # Remove old entries outside the window
            await pipe.zremrangebyscore(key, 0, window_start)
            # Count current entries
            await pipe.zcard(key)
            # Add new entry
            await pipe.zadd(key, {str(now): now})
            # Set expiry on the key
            await pipe.expire(key, window_seconds)
            results = await pipe.execute()

        current_count = results[1]  # zcard result

        if current_count >= max_requests:
            logger.warning(
                "Rate limit exceeded: user_id=%s endpoint=%s count=%d limit=%d",
                user_id, endpoint, current_count, max_requests,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s for /{endpoint}.",
            )
        await r.aclose()

    except ImportError:
        # redis library not installed — use in-memory fallback
        _check_in_memory(key, now, window_start, max_requests, endpoint, window_seconds)

    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise  # Re-raise rate limit 429
        # Redis connection error — fall back to in-memory
        logger.warning("Redis unavailable, using in-memory rate limiter: %s", exc)
        _check_in_memory(key, now, window_start, max_requests, endpoint, window_seconds)


def _check_in_memory(
    key: str, now: float, window_start: float,
    max_requests: int, endpoint: str, window_seconds: int,
) -> None:
    """In-memory sliding window rate limiter (single-process only)."""
    if key not in _in_memory_store:
        _in_memory_store[key] = []

    # Clean old entries
    _in_memory_store[key] = [t for t in _in_memory_store[key] if t > window_start]

    if len(_in_memory_store[key]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s for /{endpoint}.",
        )

    _in_memory_store[key].append(now)


def reset_in_memory_store() -> None:
    """Reset the in-memory store (for testing)."""
    _in_memory_store.clear()
