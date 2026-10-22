from datetime import datetime, timezone


def test_sync_idempotent(client, auth_headers):
    payload = {
        "transactions": [
            {
                "local_id": "local-abc-1",
                "place": "Padaria",
                "amount": 12.5,
                "category": "alimentacao",
                "is_essential": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_notification": "test",
            }
        ]
    }
    first = client.post("/transactions/sync", json=payload, headers=auth_headers)
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.json()[0]["local_id"] == "local-abc-1"

    second = client.post("/transactions/sync", json=payload, headers=auth_headers)
    assert second.status_code == 200
    assert len(second.json()) == 1


def test_patch_transaction_fields(client, auth_headers):
    sync = client.post(
        "/transactions/sync",
        json={
            "transactions": [
                {
                    "local_id": "local-patch-1",
                    "place": "Mercado",
                    "amount": 100.0,
                    "category": "mercado",
                    "is_essential": True,
                    "timestamp": datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
                }
            ]
        },
        headers=auth_headers,
    )
    assert sync.status_code == 200

    patch = client.patch(
        "/transactions/local-patch-1",
        json={
            "place": "Mercado Atualizado",
            "amount": 85.5,
            "is_essential": False,
            "category": "compras",
        },
        headers=auth_headers,
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["place"] == "Mercado Atualizado"
    assert body["amount"] == 85.5
    assert body["is_essential"] is False
    assert body["category"] == "compras"


def test_list_transactions_pagination(client, auth_headers):
    for i in range(3):
        resp = client.post(
            "/transactions/sync",
            json={
                "transactions": [
                    {
                        "local_id": f"local-list-{i}",
                        "place": f"Loja {i}",
                        "amount": float(i + 1),
                        "category": "outros",
                        "is_essential": True,
                        "timestamp": datetime(
                            2026, 6, 1, 10, i, tzinfo=timezone.utc
                        ).isoformat(),
                        "raw_notification": f"raw-{i}",
                    }
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    listed = client.get("/transactions?limit=2&offset=0", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 2
    assert body[0]["local_id"] == "local-list-2"
    assert body[0]["raw_notification"] == "raw-2"

    page2 = client.get("/transactions?limit=2&offset=2", headers=auth_headers)
    assert page2.status_code == 200
    assert len(page2.json()) == 1


def test_list_transactions_requires_auth(client):
    resp = client.get("/transactions")
    assert resp.status_code in (401, 403)


def test_patch_unknown_transaction(client, auth_headers):
    resp = client.patch(
        "/transactions/nao-existe",
        json={"amount": 1.0},
        headers=auth_headers,
    )
    assert resp.status_code == 404
