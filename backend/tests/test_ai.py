from services.ai_service import AIServiceError


def make_project(client, headers):
    return client.post("/projects", json={"name": "AI test"}, headers=headers).json()["id"]


def test_requires_login(client):
    r = client.post("/ai/explain", json={"code": "x = 1", "language": "python"})
    assert r.status_code == 401


def test_explain_returns_model_answer(client, auth, monkeypatch):
    monkeypatch.setattr("routes.ai.ask_ai", lambda system, messages: "It adds numbers.")
    r = client.post(
        "/ai/explain",
        json={"code": "def add(a, b): return a + b", "language": "python"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["result"] == "It adds numbers."


def test_provider_failure_returns_502(client, auth, monkeypatch):
    def down(system, messages):
        raise AIServiceError("model is down")

    monkeypatch.setattr("routes.ai.ask_ai", down)
    r = client.post("/ai/explain", json={"code": "x = 1", "language": "python"}, headers=auth)
    assert r.status_code == 502
    assert "model is down" in r.json()["detail"]


def test_oversized_input_rejected(client, auth):
    r = client.post(
        "/ai/explain",
        json={"code": "x" * 20001, "language": "python"},
        headers=auth,
    )
    assert r.status_code == 413


def test_chat_saves_plain_history(client, auth, monkeypatch):
    monkeypatch.setattr("routes.ai.ask_ai", lambda system, messages: "A decorator wraps a function.")
    monkeypatch.setattr("routes.ai.project_context", lambda project, query: "")
    pid = make_project(client, auth)

    r = client.post(
        "/ai/chat",
        json={"project_id": pid, "message": "What is a decorator?"},
        headers=auth,
    )
    assert r.status_code == 200

    history = client.get(f"/ai/history/{pid}", headers=auth).json()
    assert [(m["role"], m["content"]) for m in history] == [
        ("user", "What is a decorator?"),
        ("assistant", "A decorator wraps a function."),
    ]


def test_chat_on_someone_elses_project_is_404(client, auth, other_auth):
    pid = make_project(client, auth)
    r = client.post("/ai/chat", json={"project_id": pid, "message": "hi"}, headers=other_auth)
    assert r.status_code == 404
    assert client.get(f"/ai/history/{pid}", headers=other_auth).status_code == 404