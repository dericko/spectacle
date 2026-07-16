from spectacle_education.lesson_plan import SceneSpec
from spectacle_education.timing import infer_durations


def _mk(n_words):
    return SceneSpec(scene_id="s", type="concept_explanation", render_hint="layout",
                     content=" ".join(["w"] * n_words))


def test_distributes_total_by_content_volume():
    scenes = [_mk(10), _mk(30)]
    infer_durations(scenes, total_target_minutes=4)  # 240s
    assert abs(sum(s.target_duration_s for s in scenes) - 240) < 1.0
    assert scenes[1].target_duration_s > scenes[0].target_duration_s  # more words → longer


def test_positive_durations_without_a_target():
    scenes = [_mk(5), _mk(20)]
    infer_durations(scenes, total_target_minutes=None)
    assert all(s.target_duration_s > 0 for s in scenes)
