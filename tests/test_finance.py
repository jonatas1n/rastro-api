def test_get_profile_not_found(client, auth_headers):
    resp = client.get("/finance/profile", headers=auth_headers)
    assert resp.status_code == 404


def test_upsert_and_get_profile(client, auth_headers):
    payload = {
        "monthly_income": 8500.0,
        "pay_day": 5,
        "cycle_end_day": 4,
        "weekly_limit_enabled": True,
        "weekly_spending_limit": 400.0,
        "monthly_limit_enabled": False,
        "monthly_spending_limit": None,
        "month_end_balance_enabled": True,
        "month_end_target_balance": 1200.0,
    }
    put = client.put("/finance/profile", json=payload, headers=auth_headers)
    assert put.status_code == 200
    body = put.json()
    assert body["monthly_income"] == 8500.0
    assert body["pay_day"] == 5
    assert body["weekly_spending_limit"] == 400.0

    get = client.get("/finance/profile", headers=auth_headers)
    assert get.status_code == 200
    assert get.json()["month_end_target_balance"] == 1200.0

    updated = {**payload, "monthly_income": 9000.0}
    put2 = client.put("/finance/profile", json=updated, headers=auth_headers)
    assert put2.status_code == 200
    assert put2.json()["monthly_income"] == 9000.0


def test_finance_profile_requires_auth(client):
    resp = client.get("/finance/profile")
    assert resp.status_code in (401, 403)
