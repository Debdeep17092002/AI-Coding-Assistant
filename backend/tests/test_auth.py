import uuid


def new_email():
    return f"user_{uuid.uuid4().hex[:8]}@example.com"


def test_register_login_and_me(client):
    email = new_email()
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 201
    assert r.json()["email"] == email
    assert "hashed_password" not in r.text

    r = client.post("/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_duplicate_email_rejected(client):
    email = new_email()
    body = {"email": email, "password": "password123"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 400


def test_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": new_email(), "password": "short"})
    assert r.status_code == 400


def test_wrong_password_rejected(client):
    email = new_email()
    client.post("/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/auth/login", data={"username": email, "password": "wrong-password"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    bad = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert bad.status_code == 401