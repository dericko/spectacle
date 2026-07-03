from spectacle_education.spec import EducationSpec
from spectacle_education.structure_agent import structure


def _spec() -> EducationSpec:
    return EducationSpec(
        learning_objective="add fractions with unlike denominators",
        worked_example_expression="3/4 + 1/8",
        target_duration_minutes=5,
        audience="6th grade",
    )


def _fake_content_hint(spec, stub):
    return f"FAKE HINT for {stub.scene_id}"


def _fake_guided_practice_expression(spec):
    return "1/2 + 1/4"


def test_structure_sets_spec_hash_deterministically():
    from spectacle_core.hashing import content_hash
    spec = _spec()
    tree = structure(
        spec,
        guided_practice_expression_fn=_fake_guided_practice_expression,
        content_hint_fn=_fake_content_hint,
    )
    assert tree.spec_hash == content_hash(spec.model_dump(mode="json"))


def test_worked_example_gets_the_spec_expression():
    tree = structure(
        _spec(),
        guided_practice_expression_fn=_fake_guided_practice_expression,
        content_hint_fn=_fake_content_hint,
    )
    we = next(s for s in tree.scenes if s.scene_id.startswith("worked_example"))
    assert we.expression == "3/4 + 1/8"


def test_guided_practice_gets_an_llm_supplied_expression():
    def fake_guided_practice_expression(spec):
        return "1/2 + 1/4"

    tree = structure(
        _spec(),
        guided_practice_expression_fn=fake_guided_practice_expression,
        content_hint_fn=_fake_content_hint,
    )
    practice_scenes = [s for s in tree.scenes if s.scene_id.startswith("guided_practice")]
    assert practice_scenes, "5-minute lesson should include at least one guided_practice scene"
    assert all(s.expression == "1/2 + 1/4" for s in practice_scenes)


def test_content_hint_fn_is_used_to_enrich_every_scene():
    def fake_content_hint(spec, stub):
        return f"FAKE HINT for {stub.scene_id}"

    tree = structure(
        _spec(),
        content_hint_fn=fake_content_hint,
        guided_practice_expression_fn=_fake_guided_practice_expression,
    )
    for stub in tree.scenes:
        assert stub.content_hint == f"FAKE HINT for {stub.scene_id}"


def test_layout_scenes_never_get_an_expression():
    tree = structure(
        _spec(),
        guided_practice_expression_fn=_fake_guided_practice_expression,
        content_hint_fn=_fake_content_hint,
    )
    for stub in tree.scenes:
        if stub.render_hint == "layout":
            assert stub.expression is None
