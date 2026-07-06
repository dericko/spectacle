from unittest.mock import patch

from server.run_manager import RunManager


def test_start_run_returns_a_run_id_and_kicks_off_a_background_thread(tmp_path):
    manager = RunManager(artifact_root=tmp_path, pg_conn="postgresql://spectacle:spectacle@localhost:5432/spectacle")
    with patch.object(manager, "_execute_run") as mock_execute:
        run_id = manager.start_run(
            spec={"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
                    "target_duration_minutes": 1, "audience": "6th grade"},
            run_mode="auto",
        )
    assert run_id
    mock_execute.assert_called_once()
