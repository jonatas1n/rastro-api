from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models.db import User
from ..schemas import TokenResponse, UserLogin, UserRegister
from ..services.auth import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserRegister, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.email == body.email.lower())).first():
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    user = User(
        email=body.email.lower().strip(),
        name=body.name,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return TokenResponse(
        access_token=create_token(user.id),
        user_id=user.id,
        name=user.name,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email.lower().strip())).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return TokenResponse(
        access_token=create_token(user.id),
        user_id=user.id,
        name=user.name,
    )
