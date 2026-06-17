"""Entrada ASGI para a Vercel."""
from app.database import create_db
from app.main import app

__all__ = ["app"]

create_db()
