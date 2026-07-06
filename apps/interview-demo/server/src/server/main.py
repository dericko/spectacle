import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from server.run_manager import RunManager

app = FastAPI()

run_manager = RunManager(
    artifact_root=Path(os.environ.get("SPECTACLE_ARTIFACT_ROOT", "./artifacts")),
    pg_conn=os.environ.get("SPECTACLE_PG_CONN", "postgresql://spectacle:spectacle@localhost:5432/spectacle"),
)


class StartRunRequest(BaseModel):
    spec: dict
    run_mode: str = "accept_edits"


@app.post("/runs", status_code=201)
def post_runs(req: StartRunRequest) -> dict:
    run_id = run_manager.start_run(req.spec, req.run_mode)
    return {"run_id": run_id}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    status = run_manager.get_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")
    return status


@app.get("/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str) -> list[dict]:
    return run_manager.list_artifacts(run_id)
