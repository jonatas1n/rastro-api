from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models.db import Transaction, User
from ..schemas import (
    CategoryFeedback,
    CategorySuggestion,
    TransactionBatch,
    TransactionOut,
    TransactionUpdate,
)
from ..services.auth import get_current_user
from ..services.categorization import categorize, learn_from_feedback
from ..services.messages import evaluate_transaction, evaluate_spending_variation
from ..services.notification_pipeline import find_recent_duplicate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    txs = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [TransactionOut.model_validate(t) for t in txs]


@router.post("/sync", response_model=list[TransactionOut])
async def sync_batch(
    body: TransactionBatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    saved: list[TransactionOut] = []
    had_new = False

    for item in body.transactions:
        existing = session.exec(
            select(Transaction).where(
                Transaction.local_id == item.local_id,
                Transaction.user_id == user.id,
            )
        ).first()
        if existing:
            saved.append(TransactionOut.model_validate(existing))
            continue

        if user.id is not None:
            duplicate = find_recent_duplicate(
                session,
                user.id,
                item.amount,
                item.place,
                item.timestamp,
            )
            if duplicate is not None and duplicate.id is not None:
                saved.append(
                    TransactionOut(
                        id=duplicate.id,
                        local_id=item.local_id,
                        place=duplicate.place,
                        amount=duplicate.amount,
                        category=duplicate.category,
                        is_essential=duplicate.is_essential,
                        timestamp=duplicate.timestamp,
                        raw_notification=duplicate.raw_notification,
                        suppressed_duplicate=True,
                    )
                )
                continue

        tx = Transaction(
            local_id=item.local_id,
            user_id=user.id,
            place=item.place,
            amount=item.amount,
            category=item.category,
            is_essential=item.is_essential,
            timestamp=item.timestamp,
            raw_notification=item.raw_notification,
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)
        saved.append(TransactionOut.model_validate(tx))
        had_new = True

        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_txs = session.exec(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.timestamp >= day_start,
            )
        ).all()
        daily_total = sum(t.amount for t in daily_txs)
        non_ess_total = sum(t.amount for t in daily_txs if not t.is_essential)
        non_ess_ratio = non_ess_total / daily_total if daily_total else 0

        await evaluate_transaction(tx, user, session, daily_total, non_ess_ratio)

    if had_new:
        await evaluate_spending_variation(user, session)

    return saved


@router.patch("/{local_id}", response_model=TransactionOut)
def update_transaction(
    local_id: str,
    body: TransactionUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    tx = session.exec(
        select(Transaction).where(
            Transaction.local_id == local_id,
            Transaction.user_id == user.id,
        )
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    if body.is_essential is not None:
        tx.is_essential = body.is_essential
    if body.category is not None:
        tx.category = body.category
    if body.place is not None:
        tx.place = body.place.strip()
    if body.amount is not None:
        tx.amount = body.amount
    if body.timestamp is not None:
        tx.timestamp = body.timestamp

    session.add(tx)
    session.commit()
    session.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.post("/categorize", response_model=list[CategorySuggestion])
async def bulk_categorize(
    local_ids_and_places: list[dict],
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    results: list[CategorySuggestion] = []
    for item in local_ids_and_places:
        cat, conf, source = await categorize(item["place"], user.id, session)
        results.append(
            CategorySuggestion(
                local_id=item["local_id"],
                category=cat,
                confidence=conf,
                source=source,
            )
        )
    return results


@router.post("/feedback", status_code=204)
def category_feedback(
    body: CategoryFeedback,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    tx = session.exec(
        select(Transaction).where(
            Transaction.local_id == body.local_id,
            Transaction.user_id == user.id,
        )
    ).first()
    if tx:
        tx.category = body.category
        session.add(tx)
        session.commit()

    learn_from_feedback(tx.place if tx else body.local_id, body.category, user.id, session)
