import asyncio
import logging
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.api import chat_routes, core_routes, module_routes
from app.cache import CacheInvalidationMiddleware
from app.config import ROOT, get_settings
from app.core import RequestIdMiddleware, install_error_handlers, setup_logging
from app.db import engine, ensure_schema, session_scope
from app.models import Merchant
from app.services import briefing

setup_logging()
logger = logging.getLogger("app")


def _morning_briefings() -> None:
    """APScheduler job: proactively prepare every merchant's briefing and approvable actions."""
    with session_scope() as s:
        for mid in s.scalars(select(Merchant.id)):
            try:
                briefing.generate(s, mid, force=True)
                s.commit()
            except Exception:  # noqa: BLE001
                s.rollback()
                logger.exception("briefing job failed for merchant %s", mid)


def _warm_db() -> None:
    ensure_schema()

    def _open() -> None:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
            time.sleep(0.5)  # hold the connection so each worker opens a distinct one

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda _: _open(), range(10)))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    scheduler: BackgroundScheduler | None = None
    from app.agents.runtime import get_graph

    await asyncio.to_thread(_warm_db)  # wake Neon and open pooled connections
    await asyncio.to_thread(get_graph)  # build graph + checkpointer before first request
    if settings.enable_scheduler:
        scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
        scheduler.add_job(_morning_briefings, "cron", hour=settings.briefing_hour, minute=0, id="morning-briefing")
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
    from app.agents.runtime import shutdown

    shutdown()


def _mount_frontend(app: FastAPI) -> None:
    """Serve the Vite build on the same origin as the API. Absent during local `npm run dev`."""
    dist = ROOT / "frontend" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse | JSONResponse:
        if full_path == "api" or full_path.startswith(("api/", "media/")):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found"}}, status_code=404)
        root = dist.resolve()
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Munim AI", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=False,
        allow_methods=["GET", "POST"], allow_headers=["authorization", "content-type", "x-request-id"],
        expose_headers=["x-request-id"],
    )
    app.add_middleware(CacheInvalidationMiddleware)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.audio_dir), name="media")
    for r in (core_routes.router, chat_routes.router, module_routes.router):
        app.include_router(r)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"status": "ready"}

    _mount_frontend(app)
    return app


app = create_app()
