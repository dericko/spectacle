import pytest
from spectacle_core.renderer_routing import choose_renderer


def test_layout_routes_to_remotion():
    assert choose_renderer("layout") == "remotion"


def test_equation_morph_routes_to_manim():
    assert choose_renderer("equation_morph") == "manim"


def test_unknown_hint_raises_value_error():
    with pytest.raises(ValueError, match="no renderer mapped"):
        choose_renderer("something_new")
