from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import create_db
from .routers import analytics, auth, messages, transactions

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(messages.router)


@app.get("/health")
def health():
    backend = "turso-remote" if settings.turso_auth_token and settings.turso_database_url else "turso-local"
    return {"status": "ok", "app": settings.app_name, "database": backend}
