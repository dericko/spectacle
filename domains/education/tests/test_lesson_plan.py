import pytest
from spectacle_education.lesson_plan import SceneSpec, LessonPlan


def _scene(**kw):
    base = dict(scene_id="worked_example_1", type="worked_example",
                render_hint="equation_morph", content="add the fractions",
                verify=True, expression="3/4 + 1/8", target_duration_s=45.0,
                source="author")
    base.update(kw); return SceneSpec(**base)


def test_author_math_is_confirmed_by_default():
    assert _scene(source="author").confirmed is True


def test_draft_math_is_unconfirmed_by_default():
    assert _scene(source="intake_draft").confirmed is False


def test_draft_can_be_explicitly_confirmed():
    assert _scene(source="intake_draft", confirmed=True).confirmed is True


def test_lesson_plan_is_content_addressed():
    plan = LessonPlan(node_version="intake@abc", objectives=["add fractions"],
                      audience="grade 4", scenes=[_scene()])
    assert len(plan.compute_hash()) == 64
    # identical content → identical hash
    plan2 = LessonPlan(node_version="intake@abc", objectives=["add fractions"],
                       audience="grade 4", scenes=[_scene()])
    assert plan.compute_hash() == plan2.compute_hash()
