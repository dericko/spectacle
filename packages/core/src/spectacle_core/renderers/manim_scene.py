import json
import os

from manim import (
    DOWN, GRAY_B, LEFT, RIGHT, UP, WHITE,
    FadeIn, FadeOut, MathTex, Scene, Text, Transform, Write,
)


class EquationMorphScene(Scene):
    """Simple two-step morph: expression → stated_answer."""
    def construct(self):
        params = json.loads(os.environ["SPECTACLE_SCENE_PARAMS"])
        total = params["duration_s"]
        write_t, morph_t, hold_t = total * 0.2, total * 0.4, total * 0.4

        lhs = MathTex(params["expression"].replace(" ", ""))
        rhs = MathTex(params["stated_answer"])

        self.play(Write(lhs), run_time=write_t)
        self.play(Transform(lhs, rhs), run_time=morph_t)
        self.wait(hold_t)
        self.play(FadeOut(lhs))


class MultiStepScene(Scene):
    """Animate through a sequence of labeled equation steps.

    render_params["steps"] must be a list of {"expr": "<LaTeX>", "label": "<str>"}.
    Falls back to EquationMorphScene behaviour if steps is empty or absent.
    """
    def construct(self):
        params = json.loads(os.environ["SPECTACLE_SCENE_PARAMS"])
        steps = params.get("steps") or [
            {"expr": params.get("expression", "?"), "label": ""},
            {"expr": params.get("stated_answer", "?"), "label": "Result"},
        ]
        total = params["duration_s"]
        n = len(steps)
        # Divide time evenly; each step gets write + hold + fade.
        per_step = total / max(n, 1)
        write_t = min(0.6, per_step * 0.25)
        fade_t = min(0.4, per_step * 0.15)
        hold_t = per_step - write_t - fade_t

        for step_data in steps:
            label_str = step_data.get("label", "")
            eq = MathTex(step_data["expr"], font_size=80, color=WHITE)

            anims_in = [Write(eq, run_time=write_t)]
            label_mob = None
            if label_str:
                label_mob = Text(label_str, font_size=32, color=GRAY_B)
                label_mob.next_to(eq, UP, buff=0.7)
                anims_in.append(FadeIn(label_mob, shift=UP * 0.15, run_time=write_t))

            self.play(*anims_in)
            self.wait(hold_t)

            anims_out = [FadeOut(eq, run_time=fade_t)]
            if label_mob is not None:
                anims_out.append(FadeOut(label_mob, run_time=fade_t))
            self.play(*anims_out)
