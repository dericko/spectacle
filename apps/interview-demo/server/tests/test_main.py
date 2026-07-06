from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_post_runs_returns_201_and_a_run_id():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.start_run", return_value="run-abc"
    ):
        resp = client.post("/runs", json={
            "spec": {"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
                        "target_duration_minutes": 1, "audience": "6th grade"},
            "run_mode": "auto",
        })
    assert resp.status_code == 201
    assert resp.json()["run_id"] == "run-abc"


def test_get_run_status_404_for_unknown_run():
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404
