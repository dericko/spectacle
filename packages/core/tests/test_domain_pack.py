from spectacle_core.domain_pack import ContentTree, SceneStub


def test_scene_stub_defaults_expression_to_none():
    stub = SceneStub(
        scene_id="intro_1",
        render_hint="layout",
        content_hint="say hello",
        target_duration_s=20.0,
        verify=False,
    )
    assert stub.expression is None


def test_content_tree_holds_ordered_scenes():
    stubs = [
        SceneStub(scene_id="intro_1", render_hint="layout", content_hint="hi",
                   target_duration_s=20.0, verify=False),
        SceneStub(scene_id="worked_example_1", render_hint="equation_morph",
                   content_hint="show 3/4+1/8", target_duration_s=45.0, verify=True,
                   expression="3/4 + 1/8"),
    ]
    tree = ContentTree(spec_hash="deadbeef", scenes=stubs)
    assert [s.scene_id for s in tree.scenes] == ["intro_1", "worked_example_1"]
