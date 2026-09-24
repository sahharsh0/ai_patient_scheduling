def test_register_creates_patient_and_returns_token(client):
    resp = client.post(
        "/api/auth/register",
        json={"name": "Alice", "email": "alice@test.com", "password": "SecurePass123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "patient"
    assert "password_hash" not in body["user"]
    assert body["access_token"]


def test_register_duplicate_email_rejected(client):
    payload = {"name": "Alice", "email": "dupe@test.com", "password": "SecurePass123"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


def test_login_success_and_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"name": "Bob", "email": "bob@test.com", "password": "SecurePass123"},
    )
    ok = client.post("/api/auth/login", json={"email": "bob@test.com", "password": "SecurePass123"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = client.post("/api/auth/login", json={"email": "bob@test.com", "password": "WrongPassword"})
    assert bad.status_code == 401


def test_me_requires_valid_token(client):
    no_auth = client.get("/api/auth/me")
    assert no_auth.status_code == 401

    reg = client.post(
        "/api/auth/register",
        json={"name": "Cara", "email": "cara@test.com", "password": "SecurePass123"},
    )
    token = reg.json()["access_token"]
    ok = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == "cara@test.com"

    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert bad.status_code == 401
