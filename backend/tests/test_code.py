from services.code_runner import run_code


def post(client, path, code, language="python", headers=None):
    return client.post(path, json={"code": code, "language": language}, headers=headers)


def test_requires_login(client):
    assert post(client, "/code/run", "print(1)").status_code == 401


def test_analyze_finds_undefined_name(client, auth):
    body = post(client, "/code/analyze", "print(undefined_var)", headers=auth).json()
    assert body["ok"] is False
    assert any("undefined name" in i["message"] for i in body["issues"])


def test_analyze_finds_syntax_error(client, auth):
    body = post(client, "/code/analyze", "def f(:\n    pass", headers=auth).json()
    assert body["ok"] is False
    assert body["issues"][0]["line"] == 1


def test_run_prints_output(client, auth):
    body = post(client, "/code/run", "print('hello')", headers=auth).json()
    assert body["exit_code"] == 0
    assert "hello" in body["stdout"]


def test_run_reports_runtime_error(client, auth):
    body = post(client, "/code/run", "print(1/0)", headers=auth).json()
    assert body["exit_code"] != 0
    assert "ZeroDivisionError" in body["stderr"]


def test_unsupported_language_and_empty_code(client, auth):
    assert post(client, "/code/run", "puts 1", "ruby", headers=auth).status_code == 400
    assert post(client, "/code/run", "   ", headers=auth).status_code == 400


def test_runner_does_not_leak_secrets(client, auth):
    code = "import os\nprint(os.environ.get('SECRET_KEY'))"
    body = post(client, "/code/run", code, headers=auth).json()
    assert body["stdout"].strip() == "None"


def test_timeout_stops_infinite_loop():
    result = run_code("while True:\n    pass", "python", timeout=2)
    assert result["timed_out"] is True


def test_runner_can_be_disabled(client, auth, monkeypatch):
    monkeypatch.setattr("routes.code.RUNNER_ENABLED", False)
    assert post(client, "/code/run", "print(1)", headers=auth).status_code == 403


def test_run_and_debug_skips_ai_when_code_works(client, auth, monkeypatch):
    def boom(system, messages):
        raise AssertionError("AI should not be called for working code")

    monkeypatch.setattr("routes.code.ask_ai", boom)
    body = post(client, "/code/run-and-debug", "print('ok')", headers=auth).json()
    assert body["ai_suggestion"] is None


def test_run_and_debug_sends_real_error_to_ai(client, auth, monkeypatch):
    seen = {}

    def fake_ask(system, messages):
        seen["message"] = messages[0]["content"]
        return "FIX"

    monkeypatch.setattr("routes.code.ask_ai", fake_ask)
    body = post(client, "/code/run-and-debug", "print(1/0)", headers=auth).json()
    assert body["ai_suggestion"] == "FIX"
    assert "ZeroDivisionError" in seen["message"]