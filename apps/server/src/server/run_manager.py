import json
import threading
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from langgraph.checkpoint.postgres import PostgresSaver


def _safe_result(obj):
    """Recursively make a LangGraph result JSON-serializable."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _safe_result(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_result(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)

from server.db import ArtifactMetadataStore
from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.graph import build_graph
from spectacle_core.nodes.script_agent import default_script_llm
from spectacle_core.tts import MacSayTTSProvider
from spectacle_education import education_pack
from spectacle_education.structure_agent import (
    default_content_hint_llm,
    default_guided_practice_expression_llm,
)


class RunManager:
    def __init__(self, artifact_root: Path, pg_conn: str) -> None:
        self.artifact_root = Path(artifact_root)
        self.pg_conn = pg_conn
        self.metadata = ArtifactMetadataStore(pg_conn)
        self._statuses: dict[str, dict] = {}
        self.metadata.setup()

    def start_run(self, spec: dict, run_mode: Literal["accept_edits", "auto"], stub_llm: bool = False) -> str:
        run_id = str(uuid.uuid4())
        self._statuses[run_id] = {"status": "running"}
        name = spec.get("learning_objective") or run_id[:8]
        self.metadata.create_run(run_id, name)
        thread = threading.Thread(target=self._execute_run, args=(run_id, spec, run_mode, stub_llm), daemon=True)
        thread.start()
        return run_id

    def _execute_run(self, run_id: str, spec: dict, run_mode: str, stub_llm: bool = False) -> None:
        try:
            if stub_llm:
                from server.stub_llms import stub_content_hint, stub_guided_practice_expression, stub_script_llm
                script_fn = stub_script_llm
                content_hint_fn = stub_content_hint
                guided_practice_fn = stub_guided_practice_expression
            else:
                script_fn = default_script_llm
                content_hint_fn = default_content_hint_llm
                guided_practice_fn = default_guided_practice_expression_llm

            store = LocalFileArtifactStore(self.artifact_root)
            with PostgresSaver.from_conn_string(self.pg_conn) as checkpointer:
                checkpointer.setup()
                graph = build_graph(
                    domain_pack=education_pack, store=store,
                    tts_provider=MacSayTTSProvider(), checkpointer=checkpointer,
                    metadata_recorder=lambda h, stage, scene_id=None: self.metadata.record(run_id, h, stage, scene_id),
                    script_llm_fn=script_fn,
                    content_hint_fn=content_hint_fn,
                    guided_practice_expression_fn=guided_practice_fn,
                )
                config = {"configurable": {"thread_id": run_id}}
                result = graph.invoke({"spec": spec, "run_mode": run_mode}, config=config)
                interrupted = "__interrupt__" in result
                final_status = "paused" if interrupted else "done"
                stored: dict = {"status": final_status}
                if interrupted:
                    stored["result"] = _safe_result(result)
                self._statuses[run_id] = stored
                self.metadata.update_run_status(run_id, final_status)
        except Exception as e:
            self._statuses[run_id] = {"status": "error", "detail": str(e)}
            self.metadata.update_run_status(run_id, "error")

    def get_status(self, run_id: str) -> dict | None:
        if run_id in self._statuses:
            return self._statuses[run_id]
        # Fall back to DB after a server restart.
        run = self.metadata.get_run(run_id)
        if run is None:
            return None
        return {"status": run["status"]}

    def list_runs(self) -> list[dict]:
        rows = self.metadata.list_runs()
        for row in rows:
            if row["run_id"] in self._statuses:
                row["status"] = self._statuses[row["run_id"]]["status"]
            if hasattr(row["created_at"], "isoformat"):
                row["created_at"] = row["created_at"].isoformat()
        return rows

    def list_artifacts(self, run_id: str) -> list[dict]:
        return self.metadata.list_for_run(run_id)

    def resume_run(self, run_id: str, payload: dict) -> dict:
        from langgraph.types import Command

        thread = threading.Thread(
            target=self._execute_resume, args=(run_id, payload), daemon=True
        )
        thread.start()
        # Return immediately so the HTTP handler doesn't block during long renders.
        return self._statuses.get(run_id, {"status": "running"})

    def _execute_resume(self, run_id: str, payload: dict) -> None:
        from langgraph.types import Command

        try:
            store = LocalFileArtifactStore(self.artifact_root)
            with PostgresSaver.from_conn_string(self.pg_conn) as checkpointer:
                checkpointer.setup()
                graph = build_graph(
                    domain_pack=education_pack, store=store,
                    tts_provider=MacSayTTSProvider(), checkpointer=checkpointer,
                    metadata_recorder=lambda h, stage, scene_id=None: self.metadata.record(run_id, h, stage, scene_id),
                )
                config = {"configurable": {"thread_id": run_id}}
                result = graph.invoke(Command(resume=payload), config=config)
            interrupted = "__interrupt__" in result
            final_status = "paused" if interrupted else "done"
            stored: dict = {"status": final_status}
            if interrupted:
                stored["result"] = _safe_result(result)
            self._statuses[run_id] = stored
            self.metadata.update_run_status(run_id, final_status)
        except Exception as e:
            self._statuses[run_id] = {"status": "error", "detail": str(e)}
            self.metadata.update_run_status(run_id, "error")
