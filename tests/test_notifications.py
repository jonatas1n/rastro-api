import json
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models.db import NotificationCache
from app.services.notification_mask import build_template


def test_mask_is_stable_for_different_amounts():
    first = build_template("Compra aprovada de R$ 47,90 em IFOOD")
    second = build_template("Compra aprovada de R$ 1.234,56 em IFOOD")
    assert first.mask == second.mask == "compra aprovada de [VALOR] em ifood"
    assert first.template_hash == second.template_hash
    assert len(first.template_hash) == 64


def test_mask_replaces_dates_times_and_numbers():
    first = build_template("Debito de R$ 10,00 em 21/10/2026 as 14:30 final 4321")
    second = build_template("Debito de R$ 99,99 em 01/01/2024 as 08:05 final 9999")
    expected = "debito de [VALOR] em [DATA] as [HORA] final [NUM]"
    assert first.mask == second.mask == expected
    assert first.template_hash == second.template_hash


def test_process_rejects_package_outside_whitelist(client, auth_headers, monkeypatch):
    async def _boom(_text: str):
        raise AssertionError("IA não deveria ser chamada")

    monkeypatch.setattr("app.services.notification_pipeline._llm_extract", _boom)
    resp = client.post(
        "/notifications/process",
        json={
            "package_name": "com.example.shop",
            "title": "Loja",
            "text": "Compra de R$ 10,00 em TESTE",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is False
    assert body["reason"] == "whitelist"
    assert body["cache_hit"] is False


def test_cache_hit_uses_saved_rule_without_ai(client, auth_headers, session, monkeypatch):
    async def _boom(_text: str):
        raise AssertionError("IA não deveria ser chamada")

    monkeypatch.setattr("app.services.notification_pipeline._llm_extract", _boom)
    title = "Nubank"
    text = "Compra aprovada de R$ 47,90 em IFOOD"
    template = build_template(f"{title} {text}")
    session.add(
        NotificationCache(
            template_hash=template.template_hash,
            template_mask=template.mask,
            is_cost=True,
            extraction_rules=json.dumps(
                {
                    "amount_regex": r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})",
                    "place_regex": r"em\s+([A-Za-z0-9]+)",
                    "category": "alimentacao",
                }
            ),
        )
    )
    session.commit()

    resp = client.post(
        "/notifications/process",
        json={"package_name": "com.nu.production", "title": title, "text": text},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cache_hit"] is True
    assert body["accepted"] is True
    assert body["reason"] == "parsed"
    assert body["amount"] == 47.9
    assert body["place"] == "IFOOD"
    assert body["category"] == "alimentacao"


def test_cache_miss_stores_template_and_second_call_hits(client, auth_headers, session, monkeypatch):
    calls = {"n": 0}

    async def _fake(_text: str):
        calls["n"] += 1
        return None

    monkeypatch.setattr("app.services.notification_pipeline._llm_extract", _fake)
    payload = {
        "package_name": "com.nu.production",
        "title": "Nubank",
        "text": "Compra de R$ 18,50 em PADARIA",
    }
    first = client.post("/notifications/process", json=payload, headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["cache_hit"] is False
    assert first.json()["accepted"] is True
    assert first.json()["amount"] == 18.5
    assert calls["n"] == 1

    stored = session.exec(select(NotificationCache)).all()
    assert len(stored) == 1
    assert stored[0].is_cost is True

    second = client.post("/notifications/process", json=payload, headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert calls["n"] == 1


def test_process_flags_recent_duplicate(client, auth_headers, monkeypatch):
    async def _fake(_text: str):
        return None

    monkeypatch.setattr("app.services.notification_pipeline._llm_extract", _fake)
    now = datetime.now(timezone.utc).isoformat()
    synced = client.post(
        "/transactions/sync",
        json={
            "transactions": [
                {
                    "local_id": "local-dup-origin",
                    "place": "IFOOD",
                    "amount": 10.0,
                    "category": "alimentacao",
                    "is_essential": False,
                    "timestamp": now,
                }
            ]
        },
        headers=auth_headers,
    )
    assert synced.status_code == 200

    processed = client.post(
        "/notifications/process",
        json={
            "package_name": "com.nu.production",
            "title": "Nubank",
            "text": "Compra de R$ 10,00 em IFOOD",
        },
        headers=auth_headers,
    )
    assert processed.status_code == 200
    assert processed.json()["accepted"] is False
    assert processed.json()["reason"] == "duplicate"

    listed = client.get("/transactions", headers=auth_headers)
    assert len(listed.json()) == 1


def test_sync_suppresses_duplicate_within_window(client, auth_headers):
    now = datetime.now(timezone.utc)
    first = client.post(
        "/transactions/sync",
        json={
            "transactions": [
                {
                    "local_id": "local-sync-1",
                    "place": "Padaria",
                    "amount": 12.5,
                    "category": "alimentacao",
                    "is_essential": True,
                    "timestamp": now.isoformat(),
                }
            ]
        },
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert first.json()[0]["suppressed_duplicate"] is False

    second = client.post(
        "/transactions/sync",
        json={
            "transactions": [
                {
                    "local_id": "local-sync-2",
                    "place": "padaria",
                    "amount": 12.5,
                    "category": "alimentacao",
                    "is_essential": True,
                    "timestamp": (now + timedelta(minutes=5)).isoformat(),
                }
            ]
        },
        headers=auth_headers,
    )
    assert second.status_code == 200
    body = second.json()[0]
    assert body["local_id"] == "local-sync-2"
    assert body["suppressed_duplicate"] is True

    listed = client.get("/transactions", headers=auth_headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["local_id"] == "local-sync-1"


def test_whitelist_lists_seeded_packages(client, auth_headers):
    resp = client.get("/notifications/whitelist", headers=auth_headers)
    assert resp.status_code == 200
    names = {row["package_name"] for row in resp.json()}
    assert "com.nu.production" in names
    assert all(row["allowed"] is True for row in resp.json())
