def test_register_and_login(client):
    reg = client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "password": "senha123",
            "name": "Usuário",
        },
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["token_type"] == "bearer"
    assert body["name"] == "Usuário"
    assert "access_token" in body

    login = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "senha123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "senha123",
        "name": "A",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    dup = client.post("/auth/register", json=payload)
    assert dup.status_code == 409


def test_login_invalid_credentials(client):
    client.post(
        "/auth/register",
        json={"email": "ok@example.com", "password": "senha123", "name": "Ok"},
    )
    bad = client.post(
        "/auth/login",
        json={"email": "ok@example.com", "password": "wrong"},
    )
    assert bad.status_code == 401
