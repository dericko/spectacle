import json
import os

from manim import FadeOut, MathTex, Scene, TransformMatchingTex, Write


class EquationMorphScene(Scene):
    def construct(self):
        params = json.loads(os.environ["SPECTACLE_SCENE_PARAMS"])
        total = params["duration_s"]
        write_t, morph_t, hold_t = total * 0.2, total * 0.4, total * 0.4

        lhs = MathTex(params["expression"].replace(" ", ""))
        rhs = MathTex(params["stated_answer"])

        self.play(Write(lhs), run_time=write_t)
        self.play(TransformMatchingTex(lhs, rhs), run_time=morph_t)
        self.wait(hold_t)
        self.play(FadeOut(rhs))
