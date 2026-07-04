import subprocess
from pathlib import Path
from typing import Callable

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.models import SceneFinal, SceneGraph, SceneGraphEntry
from spectacle_core.renderers.manim_render import render_manim
from spectacle_core.renderers.remotion_render import render_remotion
from spectacle_core.tts import TTSProvider

OnArtifactFn = Callable[[str, str], None]


def fan_out_scenes(scene_graph: SceneGraph) -> list[dict]:
    return [{"scene": entry.model_dump(mode="json")} for entry in scene_graph.scenes]


def mux_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
         "-c:v", "copy", "-c:a", "aac", "-shortest", str(output_path)],
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
        preview_path = store.file_path(scene_hash, "preview.mp4")
        render_manim(entry.expression, entry.stated_answer, duration_s, preview_path, quality="preview")
        notify("scene_preview")
        render_manim(entry.expression, entry.stated_answer, duration_s, video_path, quality="final")
    else:
        render_remotion(entry.narration_text, entry.on_screen_text, duration_s, video_path)

    final_path = store.file_path(scene_hash, "scene_final.mp4")
    mux_audio_video(video_path, audio_path, final_path)
    notify("scene_final")

    return SceneFinal(scene_id=entry.scene_id, scene_input_hash=scene_hash, output_path=str(final_path))
