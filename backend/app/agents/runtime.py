"""Compiled graph singleton with a Postgres checkpointer (falls back to in-memory)."""
import logging
import threading
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agents.graph import build_graph
from app.config import get_settings

logger = logging.getLogger("agents.runtime")
_lock = threading.Lock()
_graph: Any = None
_pool: ConnectionPool | None = None


def get_graph() -> Any:
    global _graph, _pool
    if _graph is not None:
        return _graph
    with _lock:
        if _graph is not None:
            return _graph
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            _pool = ConnectionPool(
                get_settings().psycopg_url, min_size=1, max_size=4, open=True,
                kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None},
            )
            saver = PostgresSaver(_pool)  # type: ignore[arg-type]
            saver.setup()
            _graph = build_graph(saver)
            logger.info("graph ready with Postgres checkpointer")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Postgres checkpointer unavailable (%s); using in-memory", exc)
            _graph = build_graph(MemorySaver())
    return _graph


def shutdown() -> None:
    if _pool is not None:
        _pool.close()
