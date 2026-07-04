import threading
import uuid
from pathlib import Path
from typing import Literal

from langgraph.checkpoint.postgres import PostgresSaver

from server.db import ArtifactMetadataStore
from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.graph import build_graph
from spectacle_core.tts import MacSayTTSProvider
from spectacle_education import education_pack


class RunManager:
    def __init__(self, artifact_root: Path, pg_conn: str) -> None:
        self.artifact_root = Path(artifact_root)
        self.pg_conn = pg_conn
        self.metadata = ArtifactMetadataStore(pg_conn)
        self._statuses: dict[str, dict] = {}

    def start_run(self, spec: dict, run_mode: Literal["accept_edits", "auto"]) -> str:
        run_id = str(uuid.uuid4())
        self._statuses[run_id] = {"status": "running"}
        thread = threading.Thread(target=self._execute_run, args=(run_id, spec, run_mode), daemon=True)
        thread.start()
        return run_id

    def _execute_run(self, run_id: str, spec: dict, run_mode: str) -> None:
        try:
            self.metadata.setup()
            store = LocalFileArtifactStore(self.artifact_root)
            with PostgresSaver.from_conn_string(self.pg_conn) as checkpointer:
                checkpointer.setup()
                graph = build_graph(
                    domain_pack=education_pack, store=store,
                    tts_provider=MacSayTTSProvider(), checkpointer=checkpointer,
                    metadata_recorder=lambda h, stage, scene_id=None: self.metadata.record(run_id, h, stage, scene_id),
                )
                config = {"configurable": {"thread_id": run_id}}
                result = graph.invoke({"spec": spec, "run_mode": run_mode}, config=config)
                self._statuses[run_id] = {"status": "paused" if "__interrupt__" in result else "done", "result": result}
        except Exception as e:
            self._statuses[run_id] = {"status": "error", "detail": str(e)}

    def get_status(self, run_id: str) -> dict | None:
        return self._statuses.get(run_id)

    def list_artifacts(self, run_id: str) -> list[dict]:
        return self.metadata.list_for_run(run_id)
