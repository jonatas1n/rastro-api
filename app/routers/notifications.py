from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models.db import AppWhitelist, User
from ..schemas import NotificationProcessIn, NotificationProcessOut, WhitelistEntryOut
from ..services.auth import get_current_user
from ..services.notification_pipeline import process_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/whitelist", response_model=list[WhitelistEntryOut])
def list_whitelist(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if user.id is None:
        return []
    rows = session.exec(
        select(AppWhitelist).where(AppWhitelist.allowed.is_(True)).order_by(AppWhitelist.package_name)
    ).all()
    return [WhitelistEntryOut.model_validate(row) for row in rows]


@router.post("/process", response_model=NotificationProcessOut)
async def process(
    body: NotificationProcessIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if user.id is None:
        return NotificationProcessOut(accepted=False, reason="whitelist")
    result = await process_notification(
        session,
        user.id,
        body.package_name,
        body.title,
        body.text,
    )
    return NotificationProcessOut(
        accepted=result.accepted,
        reason=result.reason,
        cache_hit=result.cache_hit,
        amount=result.amount,
        place=result.place,
        category=result.category,
        template_hash=result.template_hash,
        template_mask=result.template_mask,
        is_cost=result.is_cost,
        extraction_rules=result.extraction_rules,
    )
