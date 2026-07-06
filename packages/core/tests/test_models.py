from spectacle_core.models import VersionedArtifact


class Dummy(VersionedArtifact):
    text: str


def test_compute_hash_stable_for_same_content():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@1", text="hello")
    assert a.compute_hash() == b.compute_hash()


def test_compute_hash_changes_with_node_version_even_if_content_same():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@2", text="hello")
    assert a.compute_hash() != b.compute_hash()


def test_compute_hash_changes_with_content():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@1", text="goodbye")
    assert a.compute_hash() != b.compute_hash()


from spectacle_core.models import SceneGraphEntry


def test_scene_graph_entry_hash_depends_only_on_own_fields():
    a = SceneGraphEntry(
        scene_id="intro_1", renderer="remotion", narration_text="hi",
        on_screen_text="Hi!", target_duration_s=20.0, verify=False,
    )
    b = SceneGraphEntry(
        scene_id="intro_1", renderer="remotion", narration_text="hi",
        on_screen_text="Hi!", target_duration_s=20.0, verify=False,
    )
    assert a.scene_input_hash() == b.scene_input_hash()


def test_scene_graph_entry_hash_changes_when_renderer_tag_changes():
    base = dict(
        scene_id="worked_example_1", narration_text="three quarters plus one eighth",
        on_screen_text="3/4 + 1/8", target_duration_s=45.0, verify=True,
        expression="3/4 + 1/8", stated_answer="7/8",
    )
    a = SceneGraphEntry(renderer="manim", **base)
    b = SceneGraphEntry(renderer="remotion", **base)
    assert a.scene_input_hash() != b.scene_input_hash()


def test_scene_graph_entry_hash_unaffected_by_scene_id():
    # scene_id is identity, not content -- changing it must not change the
    # cache key (two scenes with identical content but different ids should
    # still be independently cacheable by their content, but this test just
    # pins that scene_id itself is excluded from the hash inputs).
    a = SceneGraphEntry(scene_id="a", renderer="remotion", narration_text="hi",
                          on_screen_text="Hi!", target_duration_s=20.0, verify=False)
    b = SceneGraphEntry(scene_id="b", renderer="remotion", narration_text="hi",
                          on_screen_text="Hi!", target_duration_s=20.0, verify=False)
    assert a.scene_input_hash() == b.scene_input_hash()
