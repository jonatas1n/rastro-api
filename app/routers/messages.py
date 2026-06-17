from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models.db import ContextMessage, User
from ..schemas import ContextMessageOut, MessageAck
from ..services.auth import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/", response_model=list[ContextMessageOut])
def list_messages(
    unread_only: bool = True,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    stmt = select(ContextMessage).where(ContextMessage.user_id == user.id)
    if unread_only:
        stmt = stmt.where(ContextMessage.opened == False)  # noqa: E712
    stmt = stmt.order_by(ContextMessage.sent_at.desc()).limit(20)
    msgs = session.exec(stmt).all()
    return [ContextMessageOut.model_validate(m) for m in msgs]


@router.post("/ack", status_code=204)
def acknowledge(
    body: MessageAck,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    msg = session.get(ContextMessage, body.message_id)
    if msg and msg.user_id == user.id:
        msg.opened = True
        session.add(msg)
        session.commit()
