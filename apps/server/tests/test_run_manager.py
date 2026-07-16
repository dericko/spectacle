from unittest.mock import MagicMock, patch

from server.run_manager import RunManager

_PG_CONN = "postgresql://spectacle:spectacle@localhost:5433/spectacle"

_LEGACY_SPEC = {
    "learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
    "target_duration_minutes": 1, "audience": "6th grade",
}


def test_start_run_returns_a_run_id_and_kicks_off_a_background_thread(tmp_path):
    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    with patch.object(manager, "_execute_run") as mock_execute:
        run_id = manager.start_run(
            spec=_LEGACY_SPEC,
            run_mode="auto",
        )
    assert run_id
    mock_execute.assert_called_once()


def test_start_run_with_raw_input_returns_a_run_id_and_kicks_off_a_background_thread(tmp_path):
    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    with patch.object(manager, "_execute_run") as mock_execute:
        run_id = manager.start_run(
            raw_input="Teach 6th graders how to add fractions with unlike denominators.",
            run_mode="auto",
        )
    assert run_id
    mock_execute.assert_called_once()
    args = mock_execute.call_args.args
    # (run_id, raw_input, spec, run_mode, stub_llm)
    assert args[1] == "Teach 6th graders how to add fractions with unlike denominators."
    assert args[2] is None


def _mocked_build_graph_and_saver():
    """Patch context managers so _execute_run never touches a real graph/checkpointer."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {}
    build_graph_patch = patch("server.run_manager.build_graph", return_value=mock_graph)
    saver_patch = patch("server.run_manager.PostgresSaver")
    return build_graph_patch, saver_patch, mock_graph


def test_execute_run_legacy_spec_path_wires_legacy_intake_llm_from_lifted_plan(tmp_path):
    from spectacle_education.intake import lift_legacy_spec

    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    build_graph_patch, saver_patch, mock_graph = _mocked_build_graph_and_saver()
    with build_graph_patch as mock_build_graph, saver_patch as mock_saver_cls:
        mock_saver_cls.from_conn_string.return_value.__enter__.return_value = MagicMock()
        manager._execute_run("run-legacy", None, _LEGACY_SPEC, "auto")

    kwargs = mock_build_graph.call_args.kwargs
    intake_fn = kwargs["intake_llm_fn"]
    expected_plan = lift_legacy_spec(_LEGACY_SPEC).model_dump(mode="json")
    assert intake_fn("anything", []) == {"plan": expected_plan, "questions": []}
    assert intake_fn.fingerprint == "legacy_shim@0"

    invoke_state = mock_graph.invoke.call_args.args[0]
    assert invoke_state["prior_chat"] == []
    assert invoke_state["run_mode"] == "auto"


def test_execute_run_raw_input_path_passes_raw_input_through_and_no_stub_intake(tmp_path):
    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    build_graph_patch, saver_patch, mock_graph = _mocked_build_graph_and_saver()
    with build_graph_patch as mock_build_graph, saver_patch as mock_saver_cls:
        mock_saver_cls.from_conn_string.return_value.__enter__.return_value = MagicMock()
        manager._execute_run("run-raw", "teach ratios to 7th graders", None, "auto")

    kwargs = mock_build_graph.call_args.kwargs
    assert kwargs["intake_llm_fn"] is None  # falls through to graph.py's real default_intake_llm
    invoke_state = mock_graph.invoke.call_args.args[0]
    assert invoke_state["raw_input"] == "teach ratios to 7th graders"


def test_execute_run_stub_llm_raw_input_path_uses_stub_intake_llm(tmp_path):
    from server.stub_llms import stub_intake_llm

    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    build_graph_patch, saver_patch, mock_graph = _mocked_build_graph_and_saver()
    with build_graph_patch as mock_build_graph, saver_patch as mock_saver_cls:
        mock_saver_cls.from_conn_string.return_value.__enter__.return_value = MagicMock()
        manager._execute_run("run-stub", "teach ratios", None, "auto", stub_llm=True)

    kwargs = mock_build_graph.call_args.kwargs
    assert kwargs["intake_llm_fn"] is stub_intake_llm


def test_execute_run_stub_llm_legacy_spec_path_still_uses_legacy_intake_llm(tmp_path):
    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    build_graph_patch, saver_patch, mock_graph = _mocked_build_graph_and_saver()
    with build_graph_patch as mock_build_graph, saver_patch as mock_saver_cls:
        mock_saver_cls.from_conn_string.return_value.__enter__.return_value = MagicMock()
        manager._execute_run("run-stub-legacy", None, _LEGACY_SPEC, "auto", stub_llm=True)

    kwargs = mock_build_graph.call_args.kwargs
    assert kwargs["intake_llm_fn"].fingerprint == "legacy_shim@0"


def test_execute_run_distinct_legacy_specs_produce_distinct_raw_input_for_the_intake_cache_key(tmp_path):
    # intake_node's cache key is derived from state["raw_input"] (+ prior_chat + fingerprint).
    # The legacy shim's fingerprint is a constant ("legacy_shim@0") and it ignores its
    # (raw_input, prior_chat) call args entirely, so if effective_raw_input didn't vary with
    # the spec's actual content, two different legacy specs run against the same artifact
    # store would collide on the same cache key and the second run would silently be served
    # the first run's plan.
    other_spec = {
        "learning_objective": "simplify fractions", "worked_example_expression": "12/18",
        "target_duration_minutes": 2, "audience": "7th grade",
    }
    manager = RunManager(artifact_root=tmp_path, pg_conn=_PG_CONN)
    build_graph_patch, saver_patch, mock_graph = _mocked_build_graph_and_saver()

    with build_graph_patch, saver_patch as mock_saver_cls:
        mock_saver_cls.from_conn_string.return_value.__enter__.return_value = MagicMock()
        manager._execute_run("run-legacy-a", None, _LEGACY_SPEC, "auto")
        raw_input_a = mock_graph.invoke.call_args.args[0]["raw_input"]

        manager._execute_run("run-legacy-b", None, other_spec, "auto")
        raw_input_b = mock_graph.invoke.call_args.args[0]["raw_input"]

    assert raw_input_a != raw_input_b
