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
