from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from ..models.db import CategoryEnum


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email:    EmailStr
    password: str
    name:     str


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    name:         str


# ── Transaction ───────────────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    local_id:         str
    place:            str
    amount:           float
    category:         CategoryEnum
    is_essential:     bool = True
    timestamp:        datetime
    raw_notification: Optional[str] = None


class TransactionBatch(BaseModel):
    """Payload de sincronização: lista de transações pendentes."""
    transactions: list[TransactionIn]


class TransactionOut(BaseModel):
    id:               int
    local_id:         str
    place:            str
    amount:           float
    category:         CategoryEnum
    is_essential:     bool
    timestamp:        datetime
    raw_notification: Optional[str] = None
    suppressed_duplicate: bool = False

    model_config = {"from_attributes": True}


class TransactionUpdate(BaseModel):
    is_essential: Optional[bool]     = None
    category:     Optional[CategoryEnum] = None
    place:        Optional[str] = None
    amount:       Optional[float] = None
    timestamp:    Optional[datetime] = None


# ── Category ──────────────────────────────────────────────────────────────────

class CategorySuggestion(BaseModel):
    """Retorno do endpoint de categorização aprimorada."""
    local_id:   str
    category:   CategoryEnum
    confidence: float
    source:     str   # "local_rule" | "learned" | "llm"


class CategoryFeedback(BaseModel):
    """Usuário corrigiu a categoria de uma transação."""
    local_id:  str
    category:  CategoryEnum


# ── Analytics ─────────────────────────────────────────────────────────────────

class DailySummary(BaseModel):
    date:              str   # YYYY-MM-DD
    total:             float
    essential:         float
    non_essential:     float
    transaction_count: int


class CategoryBreakdown(BaseModel):
    category:    CategoryEnum
    total:       float
    count:       int
    pct_of_month: float


class MonthSummary(BaseModel):
    year:       int
    month:      int
    total:      float
    by_category: list[CategoryBreakdown]
    daily:      list[DailySummary]
    savings_potential: float  # soma dos não-essenciais


# ── Finance profile ───────────────────────────────────────────────────────────

class FinanceProfileIn(BaseModel):
    monthly_income: float = 0
    pay_day: int = Field(default=1, ge=1, le=31)
    cycle_end_day: int = Field(default=31, ge=1, le=31)
    weekly_limit_enabled: bool = False
    weekly_spending_limit: Optional[float] = None
    monthly_limit_enabled: bool = False
    monthly_spending_limit: Optional[float] = None
    month_end_balance_enabled: bool = False
    month_end_target_balance: Optional[float] = None


class FinanceProfileOut(FinanceProfileIn):
    user_id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Context Messages ──────────────────────────────────────────────────────────

class ContextMessageOut(BaseModel):
    id:      int
    trigger: str
    message: str
    sent_at: datetime
    opened:  bool

    model_config = {"from_attributes": True}


class MessageAck(BaseModel):
    message_id: int


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationProcessIn(BaseModel):
    package_name: str
    title: str = ""
    text: str = ""


class NotificationProcessOut(BaseModel):
    accepted: bool
    reason: str
    cache_hit: bool = False
    amount: Optional[float] = None
    place: Optional[str] = None
    category: Optional[CategoryEnum] = None
    template_hash: Optional[str] = None
    template_mask: Optional[str] = None
    is_cost: bool = False
    extraction_rules: Optional[str] = None


class WhitelistEntryOut(BaseModel):
    package_name: str
    display_name: str
    allowed: bool

    model_config = {"from_attributes": True}
