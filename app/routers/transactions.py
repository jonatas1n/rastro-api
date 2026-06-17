from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
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
from ..services.messages import evaluate_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/sync", response_model=list[TransactionOut])
async def sync_batch(
    body: TransactionBatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    saved: list[Transaction] = []

    for item in body.transactions:
        existing = session.exec(
            select(Transaction).where(
                Transaction.local_id == item.local_id,
                Transaction.user_id == user.id,
            )
        ).first()
        if existing:
            saved.append(existing)
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
        saved.append(tx)

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

    return [TransactionOut.model_validate(t) for t in saved]


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
