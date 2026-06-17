"""
Categorização em três camadas:

1. Regras locais (regex) — instantâneo
2. Regras aprendidas (CategoryRule no Turso) — personalizadas
3. LLM via Anthropic — fallback
"""
from __future__ import annotations

import re
from datetime import datetime

from anthropic import Anthropic
from sqlmodel import Session, select

from ..config import get_settings
from ..models.db import CategoryEnum, CategoryRule

settings = get_settings()

_LOCAL_RULES: list[tuple[re.Pattern, CategoryEnum]] = [
    (re.compile(r"ifood|rappi|uber.?eat|james|mcdonalds|burger|subway|pizza|padaria|lanchonete|restaurante|cafe|açaí", re.I), CategoryEnum.alimentacao),
    (re.compile(r"pão de açúcar|extra|carrefour|atacadão|assaí|mercado|hortifruti|supermercado|sacolão", re.I), CategoryEnum.mercado),
    (re.compile(r"\b99\b|uber|cabify|taxi|posto|shell|ipiranga|petrobras|combustível|gasolina|estacionamento|metrô", re.I), CategoryEnum.transporte),
    (re.compile(r"farmácia|drogaria|droga|panvel|ultrafarma|pacheco|hospital|clínica|laboratorio|exame|dentista|médico", re.I), CategoryEnum.saude),
    (re.compile(r"amazon|shopee|americanas|magazineluiza|magalu|renner|riachuelo|lojas|shopping|mercado.?livre", re.I), CategoryEnum.compras),
    (re.compile(r"netflix|spotify|amazon.?prime|hbo|disney|cinema|teatro|show|steam|playstation|xbox|bar|balada", re.I), CategoryEnum.lazer),
]


def _local_category(place: str) -> CategoryEnum | None:
    for pattern, cat in _LOCAL_RULES:
        if pattern.search(place):
            return cat
    return None


def _learned_category(
    place: str,
    user_id: int,
    session: Session,
) -> tuple[CategoryEnum, float] | None:
    stmt = (
        select(CategoryRule)
        .where(CategoryRule.user_id == user_id)
        .order_by(CategoryRule.confidence.desc())
    )
    place_lower = place.lower()
    for rule in session.exec(stmt).all():
        if rule.keyword.lower() in place_lower:
            return rule.category, rule.confidence
    return None


async def _llm_category(place: str) -> CategoryEnum:
    if not settings.anthropic_api_key:
        return CategoryEnum.outros

    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f'Categorize o seguinte estabelecimento brasileiro em UMA das categorias: '
        f'alimentacao, transporte, saude, compras, lazer, mercado, outros.\n'
        f'Estabelecimento: "{place}"\n'
        f'Responda APENAS com o nome da categoria, sem explicação.'
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip().lower()
    try:
        return CategoryEnum(raw)
    except ValueError:
        return CategoryEnum.outros


async def categorize(
    place: str,
    user_id: int,
    session: Session,
) -> tuple[CategoryEnum, float, str]:
    local = _local_category(place)
    if local:
        return local, 0.85, "local_rule"

    learned = _learned_category(place, user_id, session)
    if learned:
        cat, conf = learned
        return cat, conf, "learned"

    cat = await _llm_category(place)
    _upsert_rule(place, cat, user_id, session, confidence=0.5)
    return cat, 0.5, "llm"


def learn_from_feedback(
    place: str,
    category: CategoryEnum,
    user_id: int,
    session: Session,
) -> None:
    keyword = _extract_keyword(place)
    _upsert_rule(keyword, category, user_id, session, confidence=1.0, bump=True)


def _upsert_rule(
    keyword: str,
    category: CategoryEnum,
    user_id: int,
    session: Session,
    confidence: float = 1.0,
    bump: bool = False,
) -> None:
    kw = keyword.lower()[:40]
    rule = session.exec(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id,
            CategoryRule.keyword == kw,
        )
    ).first()
    if rule:
        rule.category = category
        rule.occurrences += 1
        if bump:
            rule.confidence = min(1.0, rule.confidence + 0.1)
        rule.updated_at = datetime.utcnow()
    else:
        rule = CategoryRule(
            user_id=user_id,
            keyword=kw,
            category=category,
            confidence=confidence,
        )
    session.add(rule)
    session.commit()


def _extract_keyword(place: str) -> str:
    stopwords = {"de", "do", "da", "no", "na", "em", "e", "o", "a", "os", "as"}
    words = [w for w in place.lower().split() if w not in stopwords and len(w) > 2]
    return " ".join(words[:2]) if words else place[:20]
