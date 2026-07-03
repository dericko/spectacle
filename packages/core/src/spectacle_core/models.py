from typing import Literal

from pydantic import BaseModel

from spectacle_core.hashing import content_hash


class VersionedArtifact(BaseModel):
    node_version: str

    def compute_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


class SceneNarration(BaseModel):
    scene_id: str
    render_hint: Literal["layout", "equation_morph"]
    narration_text: str
    on_screen_text: str
    target_duration_s: float
    verify: bool
    expression: str | None = None
    stated_answer: str | None = None


class Script(VersionedArtifact):
    node_version: str = "script_agent@1"
    tree_hash: str
    scenes: list[SceneNarration]


class SceneGraphEntry(BaseModel):
    scene_id: str
    renderer: Literal["remotion", "manim"]
    narration_text: str
    on_screen_text: str
    target_duration_s: float
    verify: bool
    expression: str | None = None
    stated_answer: str | None = None
    render_params: dict = {}

    def scene_input_hash(self) -> str:
        return content_hash({
            "narration_text": self.narration_text,
            "on_screen_text": self.on_screen_text,
            "renderer": self.renderer,
            "render_params": self.render_params,
            "expression": self.expression,
            "stated_answer": self.stated_answer,
        })


class SceneGraph(VersionedArtifact):
    node_version: str = "scene_planner@1"
    script_hash: str
    scenes: list[SceneGraphEntry]


class VerificationResult(BaseModel):
    scene_id: str
    scene_input_hash: str
    passed: bool
    detail: str


class NarrationClip(BaseModel):
    scene_id: str
    scene_input_hash: str
    audio_path: str
    duration_s: float


class ScenePreview(BaseModel):
    scene_id: str
    scene_input_hash: str
    video_path: str


class RenderManifest(BaseModel):
    scene_id: str
    scene_input_hash: str
    video_path: str
    duration_s: float


class SceneFinal(BaseModel):
    scene_id: str
    scene_input_hash: str
    output_path: str


class FinalManifest(VersionedArtifact):
    node_version: str = "mux_final@1"
    scene_graph_hash: str
    output_path: str
