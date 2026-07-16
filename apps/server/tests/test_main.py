from fastapi.testclient import TestClient

from server.main import app, require_api_key

# Auth is exercised separately in test_require_api_key_* below; every other
# test bypasses it via FastAPI's dependency-override mechanism so route
# behavior stays decoupled from the auth layer's own configuration.
app.dependency_overrides[require_api_key] = lambda: None

client = TestClient(app)


def test_post_runs_with_legacy_spec_returns_201_and_a_run_id():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.start_run", return_value="run-abc"
    ) as mock_start:
        resp = client.post("/runs", json={
            "spec": {"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
                        "target_duration_minutes": 1, "audience": "6th grade"},
            "run_mode": "auto",
        })
    assert resp.status_code == 201
    assert resp.json()["run_id"] == "run-abc"
    mock_start.assert_called_once()
    args = mock_start.call_args.args
    assert args[0] is None  # raw_input
    assert args[1]["learning_objective"] == "add fractions"  # spec


def test_post_runs_with_raw_input_returns_201_and_a_run_id():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.start_run", return_value="run-xyz"
    ) as mock_start:
        resp = client.post("/runs", json={
            "raw_input": "Teach 6th graders how to add fractions with unlike denominators.",
            "run_mode": "auto",
        })
    assert resp.status_code == 201
    assert resp.json()["run_id"] == "run-xyz"
    mock_start.assert_called_once()
    args = mock_start.call_args.args
    assert args[0] == "Teach 6th graders how to add fractions with unlike denominators."
    assert args[1] is None  # spec


def test_post_runs_400_when_neither_raw_input_nor_spec_provided():
    resp = client.post("/runs", json={"run_mode": "auto"})
    assert resp.status_code == 400


def test_post_runs_400_when_both_raw_input_and_spec_provided():
    resp = client.post("/runs", json={
        "raw_input": "teach ratios",
        "spec": {"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
                    "target_duration_minutes": 1, "audience": "6th grade"},
        "run_mode": "auto",
    })
    assert resp.status_code == 400


def test_get_run_status_404_for_unknown_run():
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_simulate_crash_calls_os_exit():
    with __import__("unittest.mock", fromlist=["patch"]).patch("server.main.os._exit") as mock_exit:
        client.post("/runs/some-run/simulate-crash")
    mock_exit.assert_called_once_with(1)


def test_resume_endpoint_delegates_to_run_manager():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.resume_run", return_value={"status": "done"}
    ) as mock_resume:
        resp = client.post("/runs/run-1/resume", json={"action": "approve"})
    mock_resume.assert_called_once_with("run-1", {"action": "approve"})
    assert resp.json() == {"status": "done"}


def test_interrupt_chat_returns_proposed_artifact():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.propose_edit", return_value={"text": "edited"}
    ):
        resp = client.post("/runs/run-1/interrupt/chat", json={
            "artifact_type": "Script", "current_artifact": {"text": "original"},
            "message": "make it punchier", "history": [],
        })
    assert resp.json() == {"proposed_artifact": {"text": "edited"}}


def test_interrupt_resume_delegates_to_run_manager_same_as_resume():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.resume_run", return_value={"status": "done"}
    ) as mock_resume:
        resp = client.post("/runs/run-1/interrupt/resume", json={"action": "approve"})
    mock_resume.assert_called_once_with("run-1", {"action": "approve"})
    assert resp.json() == {"status": "done"}


def test_get_artifact_rejects_path_traversal_content_hash():
    # %2e%2e survives client-side URL normalization (a bare ".." gets
    # collapsed by httpx before the request is even sent), so this is what
    # actually reaches the route handler's content_hash parameter.
    resp = client.get("/artifacts/%2e%2e")
    assert resp.status_code == 400


def test_get_any_artifact_file_rejects_path_traversal_content_hash():
    resp = client.get("/api/artifacts/%2e%2e/artifact.json")
    assert resp.status_code == 400


# --- require_api_key: exercised with the real dependency, not the override ---

def _client_without_auth_override():
    real_app = app
    real_app.dependency_overrides.pop(require_api_key, None)
    return TestClient(real_app)


def test_require_api_key_rejects_request_when_key_not_configured(monkeypatch):
    monkeypatch.delenv("SPECTACLE_API_KEY", raising=False)
    try:
        resp = _client_without_auth_override().get("/runs")
        assert resp.status_code == 500
    finally:
        app.dependency_overrides[require_api_key] = lambda: None


def test_require_api_key_rejects_missing_credentials(monkeypatch):
    monkeypatch.setenv("SPECTACLE_API_KEY", "secret-token")
    try:
        resp = _client_without_auth_override().get("/runs")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[require_api_key] = lambda: None


def test_require_api_key_rejects_wrong_bearer_token(monkeypatch):
    monkeypatch.setenv("SPECTACLE_API_KEY", "secret-token")
    try:
        resp = _client_without_auth_override().get(
            "/runs", headers={"authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[require_api_key] = lambda: None


def test_require_api_key_accepts_correct_bearer_token(monkeypatch):
    monkeypatch.setenv("SPECTACLE_API_KEY", "secret-token")
    try:
        resp = _client_without_auth_override().get(
            "/runs", headers={"authorization": "Bearer secret-token"},
        )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides[require_api_key] = lambda: None


def test_require_api_key_accepts_correct_query_param_token_for_sse(monkeypatch):
    monkeypatch.setenv("SPECTACLE_API_KEY", "secret-token")
    try:
        resp = _client_without_auth_override().get("/runs?api_key=secret-token")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides[require_api_key] = lambda: None
