from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class CategoryEnum(str, Enum):
    alimentacao = "alimentacao"
    transporte = "transporte"
    saude = "saude"
    compras = "compras"
    lazer = "lazer"
    mercado = "mercado"
    outros = "outros"


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    local_id: str = Field(index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    place: str
    amount: float
    category: CategoryEnum
    is_essential: bool = Field(default=True)
    timestamp: datetime
    raw_notification: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CategoryRule(SQLModel, table=True):
    __tablename__ = "category_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    keyword: str = Field(index=True)
    category: CategoryEnum
    confidence: float = Field(default=1.0)
    occurrences: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContextMessage(SQLModel, table=True):
    __tablename__ = "context_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    trigger: str
    message: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    opened: bool = Field(default=False)
