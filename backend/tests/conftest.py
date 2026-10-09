import os
import tempfile
import uuid
from pathlib import Path

# These must be set BEFORE the app is imported, so tests never touch your real database
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_tmp) / "test.db").as_posix()
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ENABLE_CODE_RUNNER"] = "true"

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def make_user(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return make_user(client)


@pytest.fixture
def other_auth(client):
    return make_user(client)