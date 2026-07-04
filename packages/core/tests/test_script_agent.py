from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.nodes.script_agent import ScriptLLMResponse, run_script_agent


def _tree() -> ContentTree:
    stubs = [
        SceneStub(scene_id="intro_1", render_hint="layout", content_hint="say hi",
                   target_duration_s=20.0, verify=False),
        SceneStub(scene_id="worked_example_1", render_hint="equation_morph",
                   content_hint="show 3/4+1/8", target_duration_s=45.0, verify=True,
                   expression="3/4 + 1/8"),
    ]
    return ContentTree(spec_hash="deadbeef", scenes=stubs)


def _fake_llm(stub: SceneStub) -> ScriptLLMResponse:
    if stub.expression is not None:
        return ScriptLLMResponse(
            narration_text=f"narration for {stub.scene_id}",
            on_screen_text=f"on-screen for {stub.scene_id}",
            stated_answer="7/8",
        )
    return ScriptLLMResponse(
        narration_text=f"narration for {stub.scene_id}",
        on_screen_text=f"on-screen for {stub.scene_id}",
    )


def test_script_has_one_scene_narration_per_stub_in_order():
    script = run_script_agent(_tree(), llm_fn=_fake_llm)
    assert [s.scene_id for s in script.scenes] == ["intro_1", "worked_example_1"]


def test_script_carries_forward_expression_and_verify():
    script = run_script_agent(_tree(), llm_fn=_fake_llm)
    we = script.scenes[1]
    assert we.expression == "3/4 + 1/8"
    assert we.verify is True
    assert we.stated_answer == "7/8"


def test_layout_scene_has_no_stated_answer():
    script = run_script_agent(_tree(), llm_fn=_fake_llm)
    intro = script.scenes[0]
    assert intro.stated_answer is None


def test_script_tree_hash_matches_content_hash_of_tree():
    from spectacle_core.hashing import content_hash
    tree = _tree()
    script = run_script_agent(tree, llm_fn=_fake_llm)
    assert script.tree_hash == content_hash(tree.model_dump(mode="json"))
