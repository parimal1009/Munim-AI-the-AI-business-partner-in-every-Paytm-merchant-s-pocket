import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.services import demo


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.config import get_settings

    get_settings().enable_scheduler = False
    from app.main import app

    with TestClient(app) as c:
        yield c  # type: ignore[misc]


@pytest.fixture()
def clean_state() -> None:
    """Reset mutable agent state for merchant 1 before and after a test."""
    with session_scope() as s:
        demo.reset_state(s, 1)
    yield
    with session_scope() as s:
        demo.reset_state(s, 1)


def _login(client: TestClient, mid: int) -> dict[str, str]:
    r = client.post("/api/auth/demo-login", json={"merchant_id": mid})
    assert r.status_code == 200
    return {"authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def auth1(client: TestClient) -> dict[str, str]:
    return _login(client, 1)


@pytest.fixture()
def auth2(client: TestClient) -> dict[str, str]:
    return _login(client, 2)
