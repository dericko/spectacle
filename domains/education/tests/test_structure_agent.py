from spectacle_education.lesson_plan import LessonPlan, SceneSpec
from spectacle_education.structure_agent import structure


def test_explicit_plan_scenes_drive_structure():  # A7
    plan = LessonPlan(node_version="intake@x", objectives=["add fractions"],
        audience="grade 4", scenes=[
            SceneSpec(scene_id="intro_1", type="intro", render_hint="layout", content="hook"),
            SceneSpec(scene_id="worked_example_1", type="worked_example",
                      render_hint="equation_morph", content="solve it", verify=True,
                      expression="3/4 + 1/8", source="author"),
        ])
    tree = structure(plan)
    assert [s.scene_id for s in tree.scenes] == ["intro_1", "worked_example_1"]
    we = next(s for s in tree.scenes if s.scene_id == "worked_example_1")
    assert we.expression == "3/4 + 1/8" and we.verify is True


def test_thin_plan_falls_back_to_menu():  # A6
    plan = LessonPlan(node_version="intake@x", objectives=["add fractions"],
        audience="grade 4", total_duration_target_minutes=3,
        worked_example_expression_hint="3/4 + 1/8", scenes=[])
    tree = structure(plan)
    names = {s.scene_id.rsplit("_", 1)[0] for s in tree.scenes}
    assert {"intro", "worked_example", "recap"} <= names  # menu mandatory scenes present


def test_structure_sets_spec_hash_deterministically():
    from spectacle_core.hashing import content_hash
    plan = LessonPlan(node_version="intake@x", objectives=["add fractions"],
        audience="grade 4", total_duration_target_minutes=3,
        worked_example_expression_hint="3/4 + 1/8", scenes=[])
    tree = structure(plan)
    assert tree.spec_hash == content_hash(plan.model_dump(mode="json"))


def test_thin_plan_fallback_worked_example_carries_the_hinted_expression():
    plan = LessonPlan(node_version="intake@x", objectives=["add fractions"],
        audience="grade 4", total_duration_target_minutes=3,
        worked_example_expression_hint="3/4 + 1/8", scenes=[])
    tree = structure(plan)
    we = next(s for s in tree.scenes if s.scene_id.startswith("worked_example"))
    assert we.expression == "3/4 + 1/8"
