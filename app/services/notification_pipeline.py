"""Whitelist, cache de template, extração e duplicata de notificações."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from anthropic import Anthropic
from sqlmodel import Session, select

from ..config import get_settings
from ..models.db import AppWhitelist, CategoryEnum, NotificationCache, Transaction
from .notification_mask import build_template

logger = logging.getLogger(__name__)
settings = get_settings()

DUPLICATE_WINDOW_HOURS = 6

DEFAULT_AMOUNT_REGEX = (
    r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)"
    r"|R\$\s*(\d+(?:,\d{2})?)"
    r"|(\d{1,3}(?:\.\d{3})*,\d{2})"
)
DEFAULT_PLACE_REGEX = (
    r"(?:em|no|na|estabelecimento)\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 .&'*_-]{1,60})"
)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Extraction:
    is_cost: bool
    amount: float | None
    place: str | None
    category: CategoryEnum
    rules: dict


def normalize_place(place: str) -> str:
    return _WHITESPACE.sub(" ", place.strip().lower())


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def package_allowed(package_name: str | None, rows: list[AppWhitelist]) -> AppWhitelist | None:
    if not package_name or not package_name.strip():
        return None
    pkg = package_name.strip().lower()
    best: AppWhitelist | None = None
    best_len = -1
    for row in rows:
        if not row.allowed:
            continue
        needle = row.package_name.strip().lower()
        if not needle:
            continue
        if pkg != needle and needle not in pkg:
            continue
        if len(needle) > best_len:
            best = row
            best_len = len(needle)
    return best


def _allowed_rows(session: Session) -> list[AppWhitelist]:
    return list(session.exec(select(AppWhitelist).where(AppWhitelist.allowed.is_(True))).all())


def parse_brl_amount(raw: str) -> float | None:
    cleaned = raw.strip().replace("R$", "").replace("r$", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _capture_groups(pattern: str, text: str) -> list[str]:
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return []
    match = compiled.search(text)
    if match is None:
        return []
    return [group for group in match.groups() if group]


def extract_amount(text: str, pattern: str | None) -> float | None:
    patterns = [pattern, DEFAULT_AMOUNT_REGEX]
    seen: set[str] = set()
    for candidate in patterns:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        for group in _capture_groups(candidate, text):
            amount = parse_brl_amount(group)
            if amount is not None:
                return amount
    return None


def extract_place(text: str, pattern: str | None) -> str | None:
    patterns = [pattern, DEFAULT_PLACE_REGEX]
    seen: set[str] = set()
    for candidate in patterns:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        groups = _capture_groups(candidate, text)
        if not groups:
            continue
        place = groups[0].strip(" .,-")
        if place:
            return place[:80]
    return None


def _category_or_outros(raw: object) -> CategoryEnum:
    if not isinstance(raw, str):
        return CategoryEnum.outros
    try:
        return CategoryEnum(raw.strip().lower())
    except ValueError:
        return CategoryEnum.outros


def _compile_pattern(pattern: object) -> str | None:
    if not isinstance(pattern, str) or not pattern.strip():
        return None
    try:
        re.compile(pattern)
    except re.error:
        return None
    return pattern


def _rules_payload(
    amount_regex: str,
    place_regex: str,
    category: CategoryEnum,
) -> dict:
    return {
        "amount_regex": amount_regex,
        "place_regex": place_regex,
        "category": category.value,
    }


def _deterministic(text: str) -> Extraction:
    amount = extract_amount(text, DEFAULT_AMOUNT_REGEX)
    place = extract_place(text, DEFAULT_PLACE_REGEX)
    category = CategoryEnum.outros
    return Extraction(
        is_cost=amount is not None,
        amount=amount,
        place=place,
        category=category,
        rules=_rules_payload(DEFAULT_AMOUNT_REGEX, DEFAULT_PLACE_REGEX, category),
    )


def _parse_llm_json(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


async def _llm_extract(text: str) -> dict | None:
    if not settings.anthropic_api_key:
        return None
    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            "Analise a notificação financeira brasileira abaixo. "
            "Responda apenas JSON com as chaves "
            "is_cost (bool), amount_regex (regex com um grupo de captura do valor BR), "
            "place_regex (regex com um grupo de captura do estabelecimento), "
            "category (uma de: alimentacao, transporte, saude, compras, lazer, mercado, outros). "
            "is_cost é false para saldo, marketing, código ou aviso sem compra.\n"
            f"Texto: {text}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_llm_json(response.content[0].text)
    except Exception:
        logger.exception("Falha ao extrair template de notificação via IA")
        return None


def _from_rules(text: str, rules: dict, is_cost: bool) -> Extraction:
    amount_regex = rules.get("amount_regex")
    place_regex = rules.get("place_regex")
    amount_pattern = amount_regex if isinstance(amount_regex, str) else DEFAULT_AMOUNT_REGEX
    place_pattern = place_regex if isinstance(place_regex, str) else DEFAULT_PLACE_REGEX
    category = _category_or_outros(rules.get("category"))
    return Extraction(
        is_cost=is_cost,
        amount=extract_amount(text, amount_pattern) if is_cost else None,
        place=extract_place(text, place_pattern) if is_cost else None,
        category=category,
        rules=_rules_payload(amount_pattern, place_pattern, category),
    )


async def resolve_extraction(text: str) -> Extraction:
    ai = await _llm_extract(text)
    if ai is None:
        return _deterministic(text)

    if not bool(ai.get("is_cost")):
        amount_regex = _compile_pattern(ai.get("amount_regex")) or DEFAULT_AMOUNT_REGEX
        place_regex = _compile_pattern(ai.get("place_regex")) or DEFAULT_PLACE_REGEX
        category = _category_or_outros(ai.get("category"))
        return Extraction(
            is_cost=False,
            amount=None,
            place=None,
            category=category,
            rules=_rules_payload(amount_regex, place_regex, category),
        )

    amount_regex = _compile_pattern(ai.get("amount_regex"))
    place_regex = _compile_pattern(ai.get("place_regex"))
    amount = extract_amount(text, amount_regex) if amount_regex else None
    if amount is None:
        return _deterministic(text)

    category = _category_or_outros(ai.get("category"))
    place = extract_place(text, place_regex) if place_regex else extract_place(text, None)
    return Extraction(
        is_cost=True,
        amount=amount,
        place=place,
        category=category,
        rules=_rules_payload(
            amount_regex or DEFAULT_AMOUNT_REGEX,
            place_regex or DEFAULT_PLACE_REGEX,
            category,
        ),
    )


def _load_rules(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def get_cached(session: Session, template_hash: str) -> NotificationCache | None:
    return session.exec(
        select(NotificationCache).where(NotificationCache.template_hash == template_hash)
    ).first()


def save_cache(
    session: Session,
    template_hash: str,
    template_mask: str,
    extraction: Extraction,
) -> NotificationCache:
    existing = get_cached(session, template_hash)
    if existing:
        return existing
    row = NotificationCache(
        template_hash=template_hash,
        template_mask=template_mask,
        is_cost=extraction.is_cost,
        extraction_rules=json.dumps(extraction.rules, ensure_ascii=False),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def find_recent_duplicate(
    session: Session,
    user_id: int,
    amount: float,
    place: str,
    moment: datetime,
) -> Transaction | None:
    if amount <= 0 or not place.strip():
        return None
    target_cents = round(amount * 100)
    target_place = normalize_place(place)
    moment_naive = _as_utc_naive(moment)
    window = timedelta(hours=DUPLICATE_WINDOW_HOURS)
    rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(200)
    ).all()
    for tx in rows:
        if round(tx.amount * 100) != target_cents:
            continue
        if normalize_place(tx.place) != target_place:
            continue
        delta = abs(moment_naive - _as_utc_naive(tx.timestamp))
        if delta <= window:
            return tx
    return None


@dataclass(frozen=True)
class ProcessResult:
    accepted: bool
    reason: str
    cache_hit: bool
    amount: float | None
    place: str | None
    category: CategoryEnum | None
    template_hash: str | None
    template_mask: str | None
    is_cost: bool
    extraction_rules: str | None


def _result_from_extraction(
    *,
    accepted: bool,
    reason: str,
    cache_hit: bool,
    template_hash: str,
    template_mask: str,
    extraction: Extraction,
    place: str | None,
) -> ProcessResult:
    rules = json.dumps(extraction.rules, ensure_ascii=False)
    return ProcessResult(
        accepted=accepted,
        reason=reason,
        cache_hit=cache_hit,
        amount=extraction.amount if accepted else None,
        place=place if accepted else None,
        category=extraction.category if accepted else None,
        template_hash=template_hash,
        template_mask=template_mask,
        is_cost=extraction.is_cost,
        extraction_rules=rules,
    )


async def process_notification(
    session: Session,
    user_id: int,
    package_name: str,
    title: str,
    text: str,
    moment: datetime | None = None,
) -> ProcessResult:
    rows = _allowed_rows(session)
    match = package_allowed(package_name, rows)
    if match is None:
        return ProcessResult(
            accepted=False,
            reason="whitelist",
            cache_hit=False,
            amount=None,
            place=None,
            category=None,
            template_hash=None,
            template_mask=None,
            is_cost=False,
            extraction_rules=None,
        )

    full_text = f"{title} {text}".strip()
    template = build_template(full_text)
    cached = get_cached(session, template.template_hash)
    cache_hit = cached is not None
    if cached is not None:
        extraction = _from_rules(full_text, _load_rules(cached.extraction_rules), cached.is_cost)
    else:
        extraction = await resolve_extraction(full_text)
        save_cache(session, template.template_hash, template.mask, extraction)

    if not extraction.is_cost or extraction.amount is None:
        return _result_from_extraction(
            accepted=False,
            reason="not_cost",
            cache_hit=cache_hit,
            template_hash=template.template_hash,
            template_mask=template.mask,
            extraction=extraction,
            place=None,
        )

    place = extraction.place or match.display_name
    when = moment or datetime.now(timezone.utc)
    duplicate = find_recent_duplicate(session, user_id, extraction.amount, place, when)
    if duplicate is not None:
        return _result_from_extraction(
            accepted=False,
            reason="duplicate",
            cache_hit=cache_hit,
            template_hash=template.template_hash,
            template_mask=template.mask,
            extraction=extraction,
            place=place,
        )

    return _result_from_extraction(
        accepted=True,
        reason="parsed",
        cache_hit=cache_hit,
        template_hash=template.template_hash,
        template_mask=template.mask,
        extraction=extraction,
        place=place,
    )
