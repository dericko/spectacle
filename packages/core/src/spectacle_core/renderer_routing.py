from typing import Literal

RENDER_HINT_TO_RENDERER: dict[str, Literal["remotion", "manim"]] = {
    "layout": "remotion",
    "equation_morph": "manim",
}


def choose_renderer(render_hint: str) -> Literal["remotion", "manim"]:
    try:
        return RENDER_HINT_TO_RENDERER[render_hint]
    except KeyError:
        raise ValueError(f"no renderer mapped for render_hint={render_hint!r}")
