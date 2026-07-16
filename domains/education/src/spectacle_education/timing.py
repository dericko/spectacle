from spectacle_education.lesson_plan import SceneSpec

_DEFAULT_WORDS_PER_SECOND = 2.5  # rough narration pace for the no-target heuristic


def infer_durations(scenes: list[SceneSpec], total_target_minutes: int | None) -> None:
    weights = [max(len(s.content.split()), 1) for s in scenes]
    if total_target_minutes:
        total_s = total_target_minutes * 60
        wsum = sum(weights)
        for s, w in zip(scenes, weights):
            s.target_duration_s = round(total_s * w / wsum, 1)
    else:
        for s, w in zip(scenes, weights):
            s.target_duration_s = round(w / _DEFAULT_WORDS_PER_SECOND, 1)
