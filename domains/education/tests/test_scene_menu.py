from spectacle_education.scene_menu import SCENE_MENU, budget_scenes


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


_OBJECTIVE = "add fractions with unlike denominators"
_WORKED_EXAMPLE_EXPRESSION = "3/4 + 1/8"


def _budget(minutes: int):
    return budget_scenes(_OBJECTIVE, _WORKED_EXAMPLE_EXPRESSION, minutes)


def _type_names(scenes) -> list[str]:
    return [s.scene_id.rsplit("_", 1)[0] for s in scenes]


def test_one_minute_lesson_has_only_the_three_mandatory_scenes():
    scenes = _budget(1)
    assert _type_names(scenes) == ["intro", "worked_example", "recap"]


def test_ten_minute_lesson_stays_in_pedagogical_order_and_adds_fillers():
    scenes = _budget(10)
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
    scenes = _budget(10)
    total_s = sum(s.target_duration_s for s in scenes)
    target_s = 10 * 60
    assert abs(total_s - target_s) <= 60


def test_only_equation_morph_scenes_carry_verify_true():
    scenes = _budget(10)
    for s in scenes:
        name = s.scene_id.rsplit("_", 1)[0]
        if name in ("worked_example", "guided_practice"):
            assert s.verify is True
            assert s.render_hint == "equation_morph"
        else:
            assert s.verify is False
            assert s.render_hint == "layout"


def test_worked_example_scene_carries_the_supplied_expression():
    # budget_scenes now receives the worked-example expression directly
    # (Task 4): the menu-fallback worked_example stub carries it so the
    # thin-plan path in structure() doesn't need to post-process stubs.
    scenes = _budget(5)
    we = next(s for s in scenes if s.scene_id.startswith("worked_example"))
    assert we.expression == _WORKED_EXAMPLE_EXPRESSION


def test_non_worked_example_scenes_have_no_expression():
    scenes = _budget(5)
    for s in scenes:
        if not s.scene_id.startswith("worked_example"):
            assert s.expression is None
