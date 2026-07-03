from spectacle_education.scene_menu import SCENE_MENU


def test_scene_menu_has_five_fixed_types():
    names = [d.name for d in SCENE_MENU]
    assert names == [
        "intro", "concept_explanation", "worked_example",
        "guided_practice", "recap",
    ]


def test_only_equation_morph_types_are_verified():
    verified = {d.name for d in SCENE_MENU if d.verify}
    assert verified == {"worked_example", "guided_practice"}


def test_only_intro_and_recap_are_non_repeatable():
    non_repeatable = {d.name for d in SCENE_MENU if not d.repeatable}
    assert non_repeatable == {"intro", "worked_example", "recap"}


from spectacle_education.scene_menu import budget_scenes
from spectacle_education.spec import EducationSpec


def _spec(minutes: int) -> EducationSpec:
    return EducationSpec(
        learning_objective="add fractions with unlike denominators",
        worked_example_expression="3/4 + 1/8",
        target_duration_minutes=minutes,
        audience="6th grade",
    )


def _type_names(scenes) -> list[str]:
    return [s.scene_id.rsplit("_", 1)[0] for s in scenes]


def test_one_minute_lesson_has_only_the_three_mandatory_scenes():
    scenes = budget_scenes(_spec(1))
    assert _type_names(scenes) == ["intro", "worked_example", "recap"]


def test_ten_minute_lesson_stays_in_pedagogical_order_and_adds_fillers():
    scenes = budget_scenes(_spec(10))
    names = _type_names(scenes)
    assert names[0] == "intro"
    assert names[-1] == "recap"
    assert "worked_example" in names
    assert names.count("concept_explanation") >= 1
    assert names.count("guided_practice") >= 1
    # pedagogical order: all concept_explanations before worked_example,
    # all guided_practice after it, recap last.
    we_index = names.index("worked_example")
    assert all(n == "concept_explanation" for n in names[1:we_index])
    assert all(n == "guided_practice" for n in names[we_index + 1:-1])


def test_ten_minute_lesson_total_duration_within_tolerance():
    scenes = budget_scenes(_spec(10))
    total_s = sum(s.target_duration_s for s in scenes)
    target_s = 10 * 60
    assert abs(total_s - target_s) <= 60


def test_only_equation_morph_scenes_carry_verify_true():
    scenes = budget_scenes(_spec(10))
    for s in scenes:
        name = s.scene_id.rsplit("_", 1)[0]
        if name in ("worked_example", "guided_practice"):
            assert s.verify is True
            assert s.render_hint == "equation_morph"
        else:
            assert s.verify is False
            assert s.render_hint == "layout"


def test_worked_example_expression_is_none_until_structure_fills_it_in():
    # budget_scenes is deterministic and domain-agnostic about *which*
    # expression to use -- structure() (Task 8) fills expression in.
    scenes = budget_scenes(_spec(5))
    for s in scenes:
        assert s.expression is None
