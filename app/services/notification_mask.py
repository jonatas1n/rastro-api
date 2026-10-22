"""Máscara estável de notificação: valores, datas e números viram placeholders."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")
_MONEY = re.compile(
    r"r\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?"
    r"|r\$\s*\d+(?:,\d{2})?"
    r"|\d{1,3}(?:\.\d{3})+,\d{2}"
    r"|\d+,\d{2}",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|\b\d{1,2}/\d{1,2}\b"
)
_TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_NUMBER = re.compile(r"\d+")


@dataclass(frozen=True)
class NotificationTemplate:
    mask: str
    template_hash: str


def normalize_mask(text: str) -> str:
    collapsed = _WHITESPACE.sub(" ", text.strip().lower())
    masked = _MONEY.sub("[VALOR]", collapsed)
    masked = _DATE.sub("[DATA]", masked)
    masked = _TIME.sub("[HORA]", masked)
    masked = _NUMBER.sub("[NUM]", masked)
    return _WHITESPACE.sub(" ", masked).strip()


def hash_mask(mask: str) -> str:
    return hashlib.sha256(mask.encode("utf-8")).hexdigest()


def build_template(text: str) -> NotificationTemplate:
    mask = normalize_mask(text)
    return NotificationTemplate(mask=mask, template_hash=hash_mask(mask))
