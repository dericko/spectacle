from pathlib import Path
from typing import Annotated, Callable, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.domain_pack import ContentTree, DomainPack
from spectacle_core.hashing import content_hash
from spectacle_core.models import FinalManifest, SceneGraph, Script
from spectacle_core.node_cache import cached_or_compute, node_input_key
from spectacle_core.nodes.finalize import collect_scenes, mux_final
from spectacle_core.nodes.interrupts import interrupt_review
from spectacle_core.nodes.render_scene import fan_out_scenes, render_scene
from spectacle_core.nodes.safety_gate import default_safety_llm, run_safety_gate
from spectacle_core.nodes.scene_planner import run_scene_planner
from spectacle_core.nodes.script_agent import default_script_llm, run_script_agent
from spectacle_core.nodes.verification_gate import run_verification_gate
from spectacle_core.tts import TTSProvider

MetadataRecorderFn = Callable[[str, str, str | None], None]


def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}


class GraphState(TypedDict):
    spec: dict
    run_mode: Literal["accept_edits", "auto"]
    content_tree: dict | None
    script: dict | None
    scene_graph: dict | None
    verification_results: list[dict]
    scene_finals: Annotated[dict[str, dict], _merge_dicts]
    final_manifest: dict | None


def build_graph(
    domain_pack: DomainPack,
    store: ArtifactStore,
    tts_provider: TTSProvider,
    checkpointer,
    script_llm_fn=default_script_llm,
    content_hint_fn=None,
    guided_practice_expression_fn=None,
    safety_llm_fn=default_safety_llm,
    metadata_recorder: MetadataRecorderFn | None = None,
):
    def record(content_hash_value: str, stage: str, scene_id: str | None = None) -> None:
        if metadata_recorder is not None:
            metadata_recorder(content_hash_value, stage, scene_id)

    def load_spec_and_structure(state: GraphState) -> dict:
        spec = domain_pack.spec_schema.model_validate(state["spec"])
        kwargs = {}
        if content_hint_fn is not None:
            kwargs["content_hint_fn"] = content_hint_fn
        if guided_practice_expression_fn is not None:
            kwargs["guided_practice_expression_fn"] = guided_practice_expression_fn
        spec_hash = content_hash(spec.model_dump(mode="json"))
        content_hint_fp = getattr(content_hint_fn, "fingerprint", "structure@stub")
        guided_practice_fp = getattr(guided_practice_expression_fn, "fingerprint", "structure@stub")
        structure_fingerprint = f"{content_hint_fp}+{guided_practice_fp}"
        key = node_input_key(spec_hash, structure_fingerprint)
        tree: ContentTree = cached_or_compute(
            store, key, lambda: domain_pack.structure(spec, **kwargs), ContentTree)
        record(tree.compute_hash(), "content_tree")
        return {"content_tree": tree.model_dump(mode="json")}

    def script_agent_node(state: GraphState) -> dict:
        tree = ContentTree.model_validate(state["content_tree"])
        tree_hash = tree.compute_hash()
        fingerprint = getattr(script_llm_fn, "fingerprint", "script_agent@stub")
        key = node_input_key(tree_hash, fingerprint)
        script = cached_or_compute(
            store, key, lambda: run_script_agent(tree, llm_fn=script_llm_fn), Script)
        record(script.compute_hash(), "script")
        return {"script": script.model_dump(mode="json")}

    def script_review_node(state: GraphState) -> dict:
        script = Script.model_validate(state["script"])
        reviewed = interrupt_review(script, Script, state["run_mode"])
        store.put_json(reviewed.compute_hash(), reviewed.model_dump(mode="json"))
        record(reviewed.compute_hash(), "script")
        return {"script": reviewed.model_dump(mode="json")}

    def safety_gate_node(state: GraphState) -> dict:
        # Runs AFTER script_review so it screens the actual text that will be
        # rendered, including any human edits made during review -- screening
        # only the pre-review draft would let an edit bypass the gate.
        script = Script.model_validate(state["script"])
        run_safety_gate(script, domain_pack.safety_profile, safety_llm_fn=safety_llm_fn)
        return {}

    def scene_planner_node(state: GraphState) -> dict:
        script = Script.model_validate(state["script"])
        scene_graph = run_scene_planner(script)
        store.put_json(scene_graph.compute_hash(), scene_graph.model_dump(mode="json"))
        record(scene_graph.compute_hash(), "scene_graph")
        return {"scene_graph": scene_graph.model_dump(mode="json")}

    def scene_graph_review_node(state: GraphState) -> dict:
        scene_graph = SceneGraph.model_validate(state["scene_graph"])
        reviewed = interrupt_review(scene_graph, SceneGraph, state["run_mode"])
        store.put_json(reviewed.compute_hash(), reviewed.model_dump(mode="json"))
        record(reviewed.compute_hash(), "scene_graph")
        return {"scene_graph": reviewed.model_dump(mode="json")}

    def verification_gate_node(state: GraphState) -> dict:
        scene_graph = SceneGraph.model_validate(state["scene_graph"])
        results = run_verification_gate(scene_graph, domain_pack)
        return {"verification_results": [r.model_dump(mode="json") for r in results]}

    def fan_out(state: GraphState) -> list[Send]:
        scene_graph = SceneGraph.model_validate(state["scene_graph"])
        return [Send("render_scene", payload) for payload in fan_out_scenes(scene_graph)]

    def render_scene_node(payload: dict) -> dict:
        scene_id = payload["scene"]["scene_id"]
        scene_final = render_scene(
            payload, store, tts_provider,
            on_artifact=lambda h, stage: record(h, stage, scene_id),
        )
        return {"scene_finals": {scene_final.scene_id: scene_final.model_dump(mode="json")}}

    def collect_scenes_node(state: GraphState) -> dict:
        scene_graph = SceneGraph.model_validate(state["scene_graph"])
        ordered = collect_scenes(state["scene_finals"], scene_graph)
        return {"scene_finals": {s.scene_id: s.model_dump(mode="json") for s in ordered}}

    def mux_final_node(state: GraphState) -> dict:
        scene_graph = SceneGraph.model_validate(state["scene_graph"])
        ordered = collect_scenes(state["scene_finals"], scene_graph)
        manifest: FinalManifest = mux_final(ordered, scene_graph.compute_hash(), store)
        # Store manifest JSON in both the canonical metadata dir and the video output dir.
        # The video dir hash is used for the DB record so the API path
        # /api/artifacts/{hash}/final.mp4 resolves to the actual file.
        final_dir_hash = Path(manifest.output_path).parent.name
        manifest_data = manifest.model_dump(mode="json")
        store.put_json(manifest.compute_hash(), manifest_data)
        store.put_json(final_dir_hash, manifest_data)
        record(final_dir_hash, "mux")
        return {"final_manifest": manifest_data}

    builder = StateGraph(GraphState)
    builder.add_node("structure", load_spec_and_structure)
    builder.add_node("script_agent", script_agent_node)
    builder.add_node("script_review", script_review_node)
    builder.add_node("safety_gate", safety_gate_node)
    builder.add_node("scene_planner", scene_planner_node)
    builder.add_node("scene_graph_review", scene_graph_review_node)
    builder.add_node("verification_gate", verification_gate_node)
    builder.add_node("render_scene", render_scene_node)
    builder.add_node("collect_scenes", collect_scenes_node)
    builder.add_node("mux_final", mux_final_node)

    builder.set_entry_point("structure")
    builder.add_edge("structure", "script_agent")
    builder.add_edge("script_agent", "script_review")
    builder.add_edge("script_review", "safety_gate")
    builder.add_edge("safety_gate", "scene_planner")
    builder.add_edge("scene_planner", "scene_graph_review")
    builder.add_edge("scene_graph_review", "verification_gate")
    builder.add_conditional_edges("verification_gate", fan_out, ["render_scene"])
    builder.add_edge("render_scene", "collect_scenes")
    builder.add_edge("collect_scenes", "mux_final")
    builder.add_edge("mux_final", END)

    return builder.compile(checkpointer=checkpointer)
