import threading
import uuid
from pathlib import Path
from typing import Literal

from langgraph.checkpoint.postgres import PostgresSaver

from server.db import ArtifactMetadataStore
from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.graph import build_graph
from spectacle_core.nodes.script_agent import default_script_llm
from spectacle_core.tts import MacSayTTSProvider
from spectacle_education import education_pack


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
                content_hint_fn = None
                guided_practice_fn = None

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
                final_status = "paused" if "__interrupt__" in result else "done"
                self._statuses[run_id] = {"status": final_status, "result": result}
                self.metadata.update_run_status(run_id, final_status)
        except Exception as e:
            self._statuses[run_id] = {"status": "error", "detail": str(e)}
            self.metadata.update_run_status(run_id, "error")

    def get_status(self, run_id: str) -> dict | None:
        return self._statuses.get(run_id)

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
            final_status = "paused" if "__interrupt__" in result else "done"
            self._statuses[run_id] = {"status": final_status, "result": result}
            self.metadata.update_run_status(run_id, final_status)
        except Exception as e:
            self._statuses[run_id] = {"status": "error", "detail": str(e)}
            self.metadata.update_run_status(run_id, "error")
