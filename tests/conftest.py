from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest")
os.environ.setdefault("TURSO_DATABASE_URL", "")
os.environ.setdefault("TURSO_AUTH_TOKEN", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import app.database as database_module  # noqa: E402

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
database_module.engine = _test_engine

import app.models.db as _models  # noqa: F401,E402

from app.database import get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.drop_all(_test_engine)
    SQLModel.metadata.create_all(_test_engine)
    yield


@pytest.fixture(autouse=True)
def _mock_evaluate_transaction(monkeypatch):
    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.routers.transactions.evaluate_transaction",
        _noop,
    )


@pytest.fixture
def session() -> Generator[Session, None, None]:
    with Session(_test_engine) as db_session:
        yield db_session


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/auth/register",
        json={
            "email": "pytest@rastro.app",
            "password": "senha-segura-123",
            "name": "Pytest",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
