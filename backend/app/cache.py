"""Tiny in-process TTL cache for read-heavy dashboard endpoints.

The database is remote, so every query costs a network round trip. Reads are cached per
merchant for a few seconds and the whole cache is dropped on any mutating request, so the
UI never shows stale data after an approval, payment or reset.
"""
import copy
import functools
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

F = TypeVar("F", bound=Callable[..., Any])

TTL_SECONDS = 60.0
_store: dict[tuple[str, int], tuple[float, Any]] = {}
_lock = threading.Lock()


def clear() -> None:
    with _lock:
        _store.clear()


def cached(name: str) -> Callable[[F], F]:
    """Cache a route's result per merchant (`mid` keyword argument) for TTL_SECONDS."""

    def deco(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (name, int(kwargs["mid"]))
            now = time.monotonic()
            with _lock:
                hit = _store.get(key)
            if hit and now - hit[0] < TTL_SECONDS:
                return copy.deepcopy(hit[1])
            value = fn(*args, **kwargs)
            with _lock:
                _store[key] = (time.monotonic(), copy.deepcopy(value))
            return value

        return wrapper  # type: ignore[return-value]

    return deco


class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    """Any non-GET request may change data, so drop all cached reads."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            clear()
        return response
