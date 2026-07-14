import json
import os

from manim import (
    DOWN, LEFT, RIGHT, UP,
    WHITE,
    Circle, FadeIn, FadeOut, Line, MathTex, Rectangle, Scene, Text,
    Transform, VGroup, Write,
    ManimColor,
    config,
)

# Match the Remotion dark-navy background so clips cut together cleanly.
_BG = ManimColor("#0b1021")
_ACCENT = ManimColor("#4ade80")   # same green as Remotion ACCENT
_LABEL_COLOR = ManimColor("#cbd5e1")   # slate-300 – more readable
_STEP_COLOR = WHITE
_RESULT_COLOR = ManimColor("#4ade80")

# Scene-type badge colors matching Remotion SCENE_META
_SCENE_COLORS = {
    "intro": ManimColor("#60a5fa"),
    "concept_explanation": ManimColor("#a78bfa"),
    "worked_example": ManimColor("#fb923c"),
    "guided_practice": ManimColor("#facc15"),
    "recap": ManimColor("#4ade80"),
}
_SCENE_LABELS = {
    "intro": "Introduction",
    "concept_explanation": "Key Concept",
    "worked_example": "Worked Example",
    "guided_practice": "Try It!",
    "recap": "Recap",
}


def _scene_accent_color(scene_type: str) -> ManimColor:
    return _SCENE_COLORS.get(scene_type, _ACCENT)


class EquationMorphScene(Scene):
    """Simple two-step morph: expression → stated_answer."""

    def construct(self):
        self.camera.background_color = _BG

        params = json.loads(os.environ["SPECTACLE_SCENE_PARAMS"])
        total = params["duration_s"]
        expression = params["expression"].replace(" ", "")
        answer = params["stated_answer"]

        write_t = min(0.6, total * 0.18)
        morph_t = min(1.2, total * 0.35)
        hold_t = total - write_t - morph_t - 0.3

        # Label header
        label = Text("Simplify", font_size=30, color=_LABEL_COLOR)
        label.to_edge(UP, buff=0.7)
        self.play(FadeIn(label, shift=DOWN * 0.1), run_time=0.25)

        lhs = MathTex(expression, font_size=96, color=_STEP_COLOR)
        rhs = MathTex(answer, font_size=96, color=_RESULT_COLOR)

        self.play(Write(lhs), run_time=write_t)
        self.wait(max(0.3, hold_t * 0.5))
        self.play(Transform(lhs, rhs), run_time=morph_t)
        self.wait(max(0.3, hold_t * 0.5))
        self.play(FadeOut(lhs), FadeOut(label), run_time=0.25)


class MultiStepScene(Scene):
    """Step-by-step equation walkthrough designed for K-8 learners.

    render_params["steps"]: list of {"expr": "<LaTeX>", "label": "<str>"}
    render_params["expression"]: source expression (shown in header)
    render_params["sceneType"]: scene type slug (e.g. "worked_example")
    """

    def construct(self):
        self.camera.background_color = _BG

        params = json.loads(os.environ["SPECTACLE_SCENE_PARAMS"])
        steps = params.get("steps") or [
            {"expr": params.get("expression", "?"), "label": ""},
            {"expr": params.get("stated_answer", "?"), "label": "Result"},
        ]
        expression = params.get("expression", "")
        scene_type = params.get("sceneType", "")
        total = params["duration_s"]
        n = len(steps)

        accent = _scene_accent_color(scene_type)
        badge_label = _SCENE_LABELS.get(scene_type, "")

        # ── Top accent bar (mirrors Remotion stripe) ───────────────────────────
        fw = config.frame_width
        bar = Rectangle(
            width=fw, height=0.055,
            fill_color=accent, fill_opacity=1, stroke_width=0,
        )
        bar.to_edge(UP, buff=0)
        self.add(bar)

        # ── Header row: badge label + "Solving expr" ───────────────────────────
        header_parts = []
        if badge_label:
            badge_text = Text(
                badge_label.upper(), font_size=20, color=accent,
                font="sans-serif", weight="BOLD",
            )
            header_parts.append(badge_text)

        if expression:
            solve_label = Text("Solving", font_size=24, color=_LABEL_COLOR)
            solve_expr = MathTex(expression, font_size=32, color=_LABEL_COLOR)
            solve_expr.next_to(solve_label, RIGHT, buff=0.2)
            solve_group = VGroup(solve_label, solve_expr)
            header_parts.append(solve_group)
        else:
            header_parts.append(Text("Step by step", font_size=24, color=_LABEL_COLOR))

        if len(header_parts) == 2:
            sep = Text("·", font_size=20, color=_LABEL_COLOR)
            header = VGroup(header_parts[0], sep, header_parts[1]).arrange(RIGHT, buff=0.3)
        else:
            header = VGroup(*header_parts)

        header.to_corner(UP + LEFT, buff=0.5)
        self.play(FadeIn(header, shift=DOWN * 0.1), run_time=0.3)

        # ── Progress dots ──────────────────────────────────────────────────────
        dot_r = 0.11
        dots_group = VGroup(*[
            Circle(radius=dot_r, color=_LABEL_COLOR, fill_opacity=0.2, stroke_width=2)
            for _ in range(n)
        ]).arrange(RIGHT, buff=0.3).to_corner(UP + RIGHT, buff=0.5)
        self.play(FadeIn(dots_group), run_time=0.2)

        # ── Time budget per step ───────────────────────────────────────────────
        per_step = (total - 0.8) / max(n, 1)
        write_t = min(0.55, per_step * 0.22)
        fade_t = min(0.35, per_step * 0.13)
        hold_t = max(0.2, per_step - write_t - fade_t)

        # ── Steps ─────────────────────────────────────────────────────────────
        for i, step_data in enumerate(steps):
            label_str = step_data.get("label", "")
            is_last = i == n - 1

            dot_color = _RESULT_COLOR if is_last else ManimColor("#60a5fa")
            dots_group[i].set_fill(dot_color, opacity=1.0)
            dots_group[i].set_stroke(dot_color)

            eq_color = _RESULT_COLOR if is_last else _STEP_COLOR
            eq = MathTex(step_data["expr"], font_size=96, color=eq_color)

            label_mob = None
            if label_str:
                label_color = _RESULT_COLOR if is_last else _LABEL_COLOR
                label_mob = Text(label_str, font_size=40, color=label_color,
                                 font="sans-serif")

            # Center label+equation as a unit
            if label_mob is not None:
                content = VGroup(label_mob, eq).arrange(DOWN, buff=0.5)
            else:
                content = eq
            content.move_to([0, -0.2, 0])

            anims_in = [Write(eq, run_time=write_t)]
            if label_mob is not None:
                anims_in.append(FadeIn(label_mob, shift=DOWN * 0.1, run_time=write_t))

            self.play(*anims_in)
            self.wait(hold_t)

            if i < n - 1:
                anims_out = [FadeOut(eq, run_time=fade_t)]
                if label_mob is not None:
                    anims_out.append(FadeOut(label_mob, run_time=fade_t))
                self.play(*anims_out)
            else:
                self.wait(0.4)
                fade_all = [FadeOut(eq), FadeOut(dots_group), FadeOut(header), FadeOut(bar)]
                if label_mob is not None:
                    fade_all.append(FadeOut(label_mob))
                self.play(*fade_all, run_time=0.4)
