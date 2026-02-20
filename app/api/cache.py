"""Simple in-memory TTL cache for API responses."""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

_cache: dict[str, tuple[float, Any]] = {}

DEFAULT_TTL = 300  # 5 minutes


def cached(ttl: int = DEFAULT_TTL):
    """Decorator that caches the return value of a function for *ttl* seconds.

    The cache key is built from the function name and its arguments.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            now = time.time()
            if key in _cache:
                expires, value = _cache[key]
                if now < expires:
                    return value
            result = func(*args, **kwargs)
            _cache[key] = (now + ttl, result)
            return result
        return wrapper
    return decorator


def clear_cache() -> int:
    """Flush the entire cache. Returns the number of evicted entries."""
    count = len(_cache)
    _cache.clear()
    return count
