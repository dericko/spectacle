# packages/core/src/spectacle_core/nodes/finalize.py
import subprocess
import tempfile
from pathlib import Path

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.hashing import content_hash
from spectacle_core.models import FinalManifest, SceneFinal, SceneGraph


def collect_scenes(scene_finals: dict[str, dict], scene_graph: SceneGraph) -> list[SceneFinal]:
    """Fan-in: Send-dispatched branches can complete in any order, so
    re-order results back into the scene graph's canonical order."""
    return [
        SceneFinal.model_validate(scene_finals[entry.scene_id])
        for entry in scene_graph.scenes
    ]


def ffmpeg_concat(inputs: list[str], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in inputs:
            f.write(f"file '{path}'\n")
        list_path = f.name
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", str(output_path)],
        check=True,
    )


def mux_final(scene_finals_ordered: list[SceneFinal], scene_graph_hash: str, store: ArtifactStore) -> FinalManifest:
    inputs = [s.output_path for s in scene_finals_ordered]
    final_hash = content_hash({"scene_graph_hash": scene_graph_hash, "scene_output_paths": inputs})
    output_path = store.file_path(final_hash, "final.mp4")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_concat(inputs, output_path)

    return FinalManifest(scene_graph_hash=scene_graph_hash, output_path=str(output_path))
