"""Mensagens contextuais inteligentes."""
from __future__ import annotations

import random
from datetime import datetime

from anthropic import Anthropic
from sqlmodel import Session, select

from ..config import get_settings
from ..models.db import CategoryEnum, ContextMessage, Transaction, User

settings = get_settings()

_TEMPLATES: dict[str, list[str]] = {
    "ifood_detected": [
        "Fazendo um lanche pelo app? Bom apetite 🍔 Mas não deixa o lanche comer o seu dinheiro todo.",
        "iFood chegando! Só lembra que os fretinhos somam no fim do mês 🚴",
    ],
    "fuel_detected": [
        "Abasteceu hoje 🚗 Quilômetros rodados, dinheiro bem investido — desde que não seja todo dia.",
    ],
    "non_essential_spike": [
        "Você marcou vários gastos como não-essenciais hoje 🤔 Tá tudo bem, só fique de olho no rastro.",
    ],
    "first_transaction_day": [
        "Primeiro gasto do dia registrado ✅ O rastro começou.",
    ],
}


def _pick_template(trigger: str, **kwargs) -> str:
    templates = _TEMPLATES.get(trigger, ["Confira seus gastos de hoje no Rastro."])
    raw = random.choice(templates)
    try:
        return raw.format(**kwargs)
    except KeyError:
        return raw


async def _llm_message(trigger: str, context: dict) -> str:
    if not settings.anthropic_api_key:
        return _pick_template(trigger, **context)

    client = Anthropic(api_key=settings.anthropic_api_key)
    system = (
        "Você é o assistente do Rastro, um app brasileiro de controle financeiro. "
        "Mensagens curtas (máx 2 frases), português brasileiro informal."
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=120,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Trigger: {trigger}\nContexto: {context}\nGere UMA mensagem push.",
            }
        ],
    )
    return resp.content[0].text.strip()


async def maybe_send(
    trigger: str,
    user: User,
    session: Session,
    context: dict | None = None,
    use_llm: bool = True,
) -> ContextMessage | None:
    ctx = context or {}
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = session.exec(
        select(ContextMessage).where(
            ContextMessage.user_id == user.id,
            ContextMessage.trigger == trigger,
            ContextMessage.sent_at >= today_start,
        )
    ).first()
    if existing:
        return None

    text = await _llm_message(trigger, ctx) if use_llm else _pick_template(trigger, **ctx)
    msg = ContextMessage(user_id=user.id, trigger=trigger, message=text)
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg


async def evaluate_transaction(
    tx: Transaction,
    user: User,
    session: Session,
    daily_total: float,
    non_essential_ratio: float,
) -> list[ContextMessage]:
    fired: list[ContextMessage] = []

    if tx.category == CategoryEnum.alimentacao and any(
        kw in tx.place.lower() for kw in ("ifood", "rappi", "uber eat", "james")
    ):
        msg = await maybe_send("ifood_detected", user, session, {"place": tx.place})
        if msg:
            fired.append(msg)

    if tx.category == CategoryEnum.transporte and any(
        kw in tx.place.lower() for kw in ("posto", "shell", "ipiranga", "petrobras")
    ):
        msg = await maybe_send("fuel_detected", user, session, {"amount": tx.amount})
        if msg:
            fired.append(msg)

    if non_essential_ratio > 0.4 and daily_total > 50:
        msg = await maybe_send(
            "non_essential_spike",
            user,
            session,
            {"pct": round(non_essential_ratio * 100)},
        )
        if msg:
            fired.append(msg)

    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = len(
        session.exec(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.timestamp >= day_start,
            )
        ).all()
    )
    if count == 1:
        msg = await maybe_send("first_transaction_day", user, session, use_llm=False)
        if msg:
            fired.append(msg)

    return fired
