"""Entrada serverless na Vercel (ASGI). Rotas na raiz via rewrite em vercel.json."""
from app.database import create_db
from app.main import app

create_db()

__all__ = ["app"]
