"""Cross-cutting concerns: logging, typed errors, request-id middleware, PII masking, clock."""
import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------- structured logging ----------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "httpcore", "urllib3", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log(logger: logging.Logger, msg: str, **fields: Any) -> None:
    logger.info(msg, extra={"extra_fields": fields})


# ---------- typed errors ----------
class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


def _error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id_ctx.get()}}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = rid
            logging.getLogger("http").info(
                f"{request.method} {request.url.path} -> {response.status_code}",
                extra={"extra_fields": {"ms": round((time.perf_counter() - start) * 1000)}},
            )
            return response
        finally:
            request_id_ctx.reset(token)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_error_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(_error_body("validation_error", str(exc.errors()[:3])), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app").exception("unhandled error")
        return JSONResponse(_error_body("internal_error", "Something went wrong"), status_code=500)


# ---------- PII masking (applied before text reaches the LLM) ----------
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{9})(?!\d)")


def mask_pii(text: str) -> str:
    return _PHONE.sub(lambda m: "XXXXXX" + m.group(1)[-4:], text)


# ---------- naive in-memory rate limiter (per merchant + bucket) ----------
_hits: dict[str, list[float]] = {}


def rate_limit(key: str, limit: int, window_s: int = 60) -> None:
    now = time.monotonic()
    hits = [t for t in _hits.get(key, []) if now - t < window_s]
    if len(hits) >= limit:
        raise RateLimitedError("Too many requests, please slow down")
    hits.append(now)
    _hits[key] = hits


def rupees(paise: int) -> float:
    return round(paise / 100, 2)


def fmt_inr(paise: int) -> str:
    return f"₹{paise / 100:,.0f}"
