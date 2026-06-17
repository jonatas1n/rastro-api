from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

settings = get_settings()


def _turso_host(database_url: str) -> str:
    url = database_url.strip()
    if url.startswith("libsql://"):
        return url.removeprefix("libsql://")
    return url


def _build_engine():
    token = settings.turso_auth_token.strip()
    remote_url = settings.turso_database_url.strip()

    if remote_url and token:
        host = _turso_host(remote_url)
        engine_url = f"sqlite+libsql://{host}?secure=true"
        connect_args = {"auth_token": token}
    else:
        engine_url = settings.turso_local_database_path
        connect_args = {}

    kwargs: dict = {"echo": settings.debug, "connect_args": connect_args}
    if os.getenv("VERCEL"):
        kwargs["poolclass"] = NullPool
    return create_engine(engine_url, **kwargs)


engine = _build_engine()


def create_db() -> None:
    from .models import db as _models  # noqa: F401 — registra tabelas no metadata

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
