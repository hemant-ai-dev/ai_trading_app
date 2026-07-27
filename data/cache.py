"""In-memory TTL cache for market data and analysis."""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class MemoryCache:
    """Simple thread-safe-enough in-process cache with TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    def get_or_set(self, key: str, ttl_seconds: float, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl_seconds)
        return value

    def clear(self) -> None:
        self._store.clear()


# Shared application cache instance
APP_CACHE = MemoryCache()
