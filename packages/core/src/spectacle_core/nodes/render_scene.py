import re
import subprocess
from pathlib import Path
from typing import Callable

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.hashing import content_hash
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

    def notify(stage: str, content_hash_value: str) -> None:
        if on_artifact is not None:
            on_artifact(content_hash_value, stage)

    # --- audio key: narration text + voice identity ---
    audio_key = entry.audio_input_hash(tts_provider.identity())
    audio_path = store.file_path(audio_key, "narration.wav")
    if store.file_exists(audio_key, "narration.wav") and store.exists(audio_key):
        duration_s = store.get_json(audio_key)["duration_s"]
    else:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        duration_s = tts_provider.synthesize(entry.narration_text, audio_path)
        store.put_json(audio_key, {"duration_s": duration_s})
    notify("narration_clip", audio_key)

    # --- video key: everything that drives the silent instructional video,
    # keyed on the synthesized duration (NOT voice) so a voice change alone
    # never invalidates the deterministic video render. ---
    duration_ms = round(duration_s * 1000)
    video_key = entry.video_input_hash(duration_ms)
    video_path = store.file_path(video_key, "video.mp4")
    if store.file_exists(video_key, "video.mp4"):
        if entry.renderer == "manim":
            notify("scene_preview", video_key)
    else:
        video_path.parent.mkdir(parents=True, exist_ok=True)
        if entry.renderer == "manim":
            render_params = dict(entry.render_params)
            render_params.setdefault("sceneType", entry.scene_id)
            steps = render_params.get("steps")
            if steps:
                render_params["stepStartTimesS"] = compute_item_start_times(
                    entry.narration_text, len(steps), duration_s,
                )
            preview_path = store.file_path(video_key, "preview.mp4")
            render_manim(entry.expression, entry.stated_answer, duration_s, preview_path,
                         quality="preview", render_params=render_params)
            notify("scene_preview", video_key)
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

    # --- final key: mux of this audio + this video ---
    final_key = content_hash({"kind": "final", "audio": audio_key, "video": video_key})
    final_path = store.file_path(final_key, "scene_final.mp4")
    if store.file_exists(final_key, "scene_final.mp4"):
        notify("scene_final", final_key)
        return SceneFinal(scene_id=entry.scene_id, scene_input_hash=final_key, output_path=str(final_path))

    final_path.parent.mkdir(parents=True, exist_ok=True)
    mux_audio_video(video_path, audio_path, final_path)
    notify("scene_final", final_key)

    return SceneFinal(scene_id=entry.scene_id, scene_input_hash=final_key, output_path=str(final_path))
