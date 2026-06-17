from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models.db import CategoryEnum, Transaction, User
from ..schemas import CategoryBreakdown, DailySummary, MonthSummary
from ..services.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/month", response_model=MonthSummary)
def month_summary(
    year: int = Query(default=None),
    month: int = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    now = datetime.utcnow()
    y = year or now.year
    m = month or now.month

    start = datetime(y, m, 1)
    if m == 12:
        end = datetime(y + 1, 1, 1)
    else:
        end = datetime(y, m + 1, 1)

    txs = session.exec(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.timestamp >= start,
            Transaction.timestamp < end,
        )
    ).all()

    total = sum(t.amount for t in txs)
    essential = sum(t.amount for t in txs if t.is_essential)
    non_essential = total - essential

    by_cat: dict[CategoryEnum, list[Transaction]] = defaultdict(list)
    for t in txs:
        by_cat[t.category].append(t)

    breakdown = [
        CategoryBreakdown(
            category=cat,
            total=sum(t.amount for t in items),
            count=len(items),
            pct_of_month=round(sum(t.amount for t in items) / total * 100, 1) if total else 0,
        )
        for cat, items in sorted(by_cat.items(), key=lambda x: -sum(t.amount for t in x[1]))
    ]

    by_day: dict[date, list[Transaction]] = defaultdict(list)
    for t in txs:
        by_day[t.timestamp.date()].append(t)

    daily = [
        DailySummary(
            date=str(d),
            total=sum(t.amount for t in items),
            essential=sum(t.amount for t in items if t.is_essential),
            non_essential=sum(t.amount for t in items if not t.is_essential),
            transaction_count=len(items),
        )
        for d, items in sorted(by_day.items())
    ]

    return MonthSummary(
        year=y,
        month=m,
        total=total,
        by_category=breakdown,
        daily=daily,
        savings_potential=non_essential,
    )
