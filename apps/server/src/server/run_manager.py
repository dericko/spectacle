import json
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
from server.job_queue import JobQueue, ThreadJobQueue
from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.graph import build_graph
from spectacle_core.nodes.safety_gate import default_safety_llm
from spectacle_core.nodes.script_agent import default_script_llm
from spectacle_core.tts import MacSayTTSProvider
from spectacle_education import education_pack
from spectacle_education.intake import lift_legacy_spec


def _legacy_intake_llm_for(spec: dict):
    """Build an intake_llm_fn that skips the real intake LLM entirely: the
    legacy 4-field spec already fully determines the plan, so there is
    nothing left for an LLM (real or stub) to compile."""
    plan_dict = lift_legacy_spec(spec).model_dump(mode="json")

    def _legacy_intake_llm(raw_input: str, prior_chat: list[dict], _plan: dict = plan_dict) -> dict:
        return {"plan": _plan, "questions": []}

    _legacy_intake_llm.fingerprint = "legacy_shim@0"
    return _legacy_intake_llm


class RunManager:
    def __init__(self, artifact_root: Path, pg_conn: str, job_queue: JobQueue | None = None) -> None:
        self.artifact_root = Path(artifact_root)
        self.pg_conn = pg_conn
        self.metadata = ArtifactMetadataStore(pg_conn)
        self._statuses: dict[str, dict] = {}
        self.job_queue = job_queue if job_queue is not None else ThreadJobQueue()
        self.metadata.setup()

    def start_run(
        self,
        raw_input: str | None = None,
        spec: dict | None = None,
        run_mode: Literal["accept_edits", "auto"] = "accept_edits",
        stub_llm: bool = False,
    ) -> str:
        run_id = str(uuid.uuid4())
        self._statuses[run_id] = {"status": "running"}
        if spec is not None:
            name = spec.get("learning_objective") or run_id[:8]
        else:
            name = (raw_input or "")[:60] or run_id[:8]
        self.metadata.create_run(run_id, name)
        self.job_queue.submit(lambda: self._execute_run(run_id, raw_input, spec, run_mode, stub_llm))
        return run_id

    def _execute_run(
        self, run_id: str, raw_input: str | None, spec: dict | None, run_mode: str, stub_llm: bool = False,
    ) -> None:
        try:
            if spec is not None:
                intake_fn = _legacy_intake_llm_for(spec)
            elif stub_llm:
                from server.stub_llms import stub_intake_llm
                intake_fn = stub_intake_llm
            else:
                intake_fn = None

            if stub_llm:
                from server.stub_llms import stub_safety_llm, stub_script_llm
                script_fn = stub_script_llm
                safety_fn = stub_safety_llm
            else:
                script_fn = default_script_llm
                safety_fn = default_safety_llm

            store = LocalFileArtifactStore(self.artifact_root)
            with PostgresSaver.from_conn_string(self.pg_conn) as checkpointer:
                checkpointer.setup()
                graph = build_graph(
                    domain_pack=education_pack, store=store,
                    tts_provider=MacSayTTSProvider(), checkpointer=checkpointer,
                    metadata_recorder=lambda h, stage, scene_id=None: self.metadata.record(run_id, h, stage, scene_id),
                    script_llm_fn=script_fn,
                    intake_llm_fn=intake_fn,
                    safety_llm_fn=safety_fn,
                )
                config = {"configurable": {"thread_id": run_id}}
                result = graph.invoke(
                    {"raw_input": raw_input or "", "prior_chat": [], "run_mode": run_mode}, config=config)
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
        self.job_queue.submit(lambda: self._execute_resume(run_id, payload))
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
