from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

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
    id:           int
    local_id:     str
    place:        str
    amount:       float
    category:     CategoryEnum
    is_essential: bool
    timestamp:    datetime

    model_config = {"from_attributes": True}


class TransactionUpdate(BaseModel):
    is_essential: Optional[bool]     = None
    category:     Optional[CategoryEnum] = None


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
