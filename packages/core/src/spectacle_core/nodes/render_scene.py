import re
import subprocess
from pathlib import Path
from typing import Callable

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.models import SceneFinal, SceneGraph, SceneGraphEntry
from spectacle_core.renderers.manim_render import render_manim
from spectacle_core.renderers.remotion_render import render_remotion
from spectacle_core.tts import TTSProvider

OnArtifactFn = Callable[[str, str], None]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def fan_out_scenes(scene_graph: SceneGraph) -> list[dict]:
    return [{"scene": entry.model_dump(mode="json")} for entry in scene_graph.scenes]


def compute_item_start_times(narration_text: str, item_count: int, duration_s: float) -> list[float]:
    """Estimate when each bullet item's sentence begins, in seconds, by
    weighting cumulative word count against total narration duration
    (TTS speaks at a roughly constant words-per-second rate).

    Prefers splitting narration_text on sentence boundaries when the
    sentence count matches item_count exactly (the script agent is
    instructed to write one sentence per item); falls back to an even
    word-count split otherwise so timing degrades gracefully.
    """
    if item_count <= 0:
        return []

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(narration_text.strip()) if s]
    if len(sentences) != item_count:
        words = narration_text.split()
        total_words = len(words) or 1
        chunk = total_words / item_count
        sentences = []
        idx = 0
        for i in range(item_count):
            end = round((i + 1) * chunk)
            sentences.append(" ".join(words[idx:end]))
            idx = end

    word_counts = [max(len(s.split()), 1) for s in sentences]
    total_words = sum(word_counts)
    start_times = []
    cumulative = 0
    for wc in word_counts:
        start_times.append(duration_s * cumulative / total_words)
        cumulative += wc
    return start_times


def mux_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> None:
    # Explicit map: Remotion embeds a silent AAC track; without -map, FFmpeg's
    # auto-selection prefers that over the narration WAV (stereo AAC > mono PCM).
    # Resample to 44100 Hz: MacSay produces 22050 Hz WAV which causes AAC
    # spectral encoding errors when re-decoded during the final concat step.
    # -video_track_timescale 90000: Manim uses timebase 1/15360; the ffmpeg
    # concat demuxer silently drops clips whose timebase differs from the first
    # clip. Force 1/90000 (Remotion's default) so all clips concatenate cleanly.
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
         "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-video_track_timescale", "90000",
         "-c:a", "aac", "-ar", "44100", "-shortest", str(output_path)],
        check=True,
    )


def render_scene(
    payload: dict,
    store: ArtifactStore,
    tts_provider: TTSProvider,
    on_artifact: OnArtifactFn | None = None,
) -> SceneFinal:
    entry = SceneGraphEntry.model_validate(payload["scene"])
    scene_hash = entry.scene_input_hash()

    def notify(stage: str) -> None:
        if on_artifact is not None:
            on_artifact(scene_hash, stage)

    if store.file_exists(scene_hash, "scene_final.mp4"):
        notify("scene_final")
        return SceneFinal(
            scene_id=entry.scene_id,
            scene_input_hash=scene_hash,
            output_path=str(store.file_path(scene_hash, "scene_final.mp4")),
        )

    audio_path = store.file_path(scene_hash, "narration.wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    duration_s = tts_provider.synthesize(entry.narration_text, audio_path)
    notify("narration_clip")

    video_path = store.file_path(scene_hash, "final.mp4")
    if entry.renderer == "manim":
        render_params = dict(entry.render_params)
        render_params.setdefault("sceneType", entry.scene_id)
        steps = render_params.get("steps")
        if steps:
            render_params["stepStartTimesS"] = compute_item_start_times(
                entry.narration_text, len(steps), duration_s,
            )
        preview_path = store.file_path(scene_hash, "preview.mp4")
        render_manim(entry.expression, entry.stated_answer, duration_s, preview_path,
                     quality="preview", render_params=render_params)
        notify("scene_preview")
        render_manim(entry.expression, entry.stated_answer, duration_s, video_path,
                     quality="final", render_params=render_params)
    else:
        render_params = dict(entry.render_params)
        render_params.setdefault("sceneType", entry.scene_id)
        items = render_params.get("items")
        if items:
            render_params["itemStartTimesS"] = compute_item_start_times(
                entry.narration_text, len(items), duration_s,
            )
        render_remotion(entry.narration_text, entry.on_screen_text, duration_s, video_path,
                        render_params=render_params)

    final_path = store.file_path(scene_hash, "scene_final.mp4")
    mux_audio_video(video_path, audio_path, final_path)
    notify("scene_final")

    return SceneFinal(scene_id=entry.scene_id, scene_input_hash=scene_hash, output_path=str(final_path))
