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


class NotificationCache(SQLModel, table=True):
    """Máscara de notificação já vista. A IA só roda no primeiro layout."""

    __tablename__ = "notifications_cache"

    id: Optional[int] = Field(default=None, primary_key=True)
    template_hash: str = Field(unique=True, index=True)
    template_mask: str
    is_cost: bool = Field(default=True)
    extraction_rules: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AppWhitelist(SQLModel, table=True):
    """Apps de banco/fintech autorizados a gerar lançamento."""

    __tablename__ = "app_whitelist"

    id: Optional[int] = Field(default=None, primary_key=True)
    package_name: str = Field(unique=True, index=True)
    display_name: str
    allowed: bool = Field(default=True)


class FinanceProfile(SQLModel, table=True):
    __tablename__ = "finance_profiles"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    monthly_income: float = Field(default=0.0)
    pay_day: int = Field(default=1)
    cycle_end_day: int = Field(default=31)
    weekly_limit_enabled: bool = Field(default=False)
    weekly_spending_limit: Optional[float] = None
    monthly_limit_enabled: bool = Field(default=False)
    monthly_spending_limit: Optional[float] = None
    month_end_balance_enabled: bool = Field(default=False)
    month_end_target_balance: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
