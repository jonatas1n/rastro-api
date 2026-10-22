from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models.db import FinanceProfile, User
from ..schemas import FinanceProfileIn, FinanceProfileOut
from ..services.auth import get_current_user

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/profile", response_model=FinanceProfileOut)
def get_profile(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    profile = session.exec(
        select(FinanceProfile).where(FinanceProfile.user_id == user.id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil financeiro não encontrado")
    return FinanceProfileOut.model_validate(profile)


@router.put("/profile", response_model=FinanceProfileOut)
def upsert_profile(
    body: FinanceProfileIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    profile = session.exec(
        select(FinanceProfile).where(FinanceProfile.user_id == user.id)
    ).first()

    data = body.model_dump()
    now = datetime.utcnow()

    if profile:
        for key, value in data.items():
            setattr(profile, key, value)
        profile.updated_at = now
    else:
        profile = FinanceProfile(user_id=user.id, **data, updated_at=now)
        session.add(profile)

    session.commit()
    session.refresh(profile)
    return FinanceProfileOut.model_validate(profile)
