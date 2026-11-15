"""SQLAlchemy engine/session, tuned for the Neon pooler."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_engine(
    _settings.sqlalchemy_url,
    pool_size=10,
    max_overflow=10,
    # The DB is remote (~350 ms RTT): pre_ping would add a full round trip to every request.
    # Instead recycle before Neon's idle timeout and keep TCP alive.
    pool_pre_ping=False,
    pool_recycle=240,
    connect_args={"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


_ADDITIVE_MIGRATIONS = (
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS expiry_date DATE",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS clearance_pct INTEGER",
)


def ensure_schema() -> None:
    """Idempotent, additive-only migrations so an existing database keeps working without a reseed."""
    with engine.begin() as conn:
        for stmt in _ADDITIVE_MIGRATIONS:
            conn.execute(text(stmt))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts, agents and scheduler jobs."""
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
