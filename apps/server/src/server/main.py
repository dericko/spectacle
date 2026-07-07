import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.run_manager import RunManager
from spectacle_core.edit_assistant import propose_edit
from spectacle_core.models import SceneGraph, Script

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

run_manager = RunManager(
    artifact_root=Path(os.environ.get("SPECTACLE_ARTIFACT_ROOT", "./artifacts")).resolve(),
    pg_conn=os.environ.get("SPECTACLE_PG_CONN", "postgresql://spectacle:spectacle@localhost:5433/spectacle"),
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


@app.post("/runs/{run_id}/simulate-crash")
def post_simulate_crash(run_id: str) -> dict:
    os._exit(1)  # pragma: no cover -- unreachable in tests, os._exit is mocked
    return {}  # pragma: no cover -- unreachable in normal operation


@app.post("/runs/{run_id}/resume")
def post_resume(run_id: str, payload: dict) -> dict:
    return run_manager.resume_run(run_id, payload)


_ARTIFACT_TYPES = {"Script": Script, "SceneGraph": SceneGraph}


class ChatEditRequest(BaseModel):
    artifact_type: str
    current_artifact: dict
    message: str
    history: list[dict] = []


@app.post("/runs/{run_id}/interrupt/chat")
def post_interrupt_chat(run_id: str, req: ChatEditRequest) -> dict:
    artifact_cls = _ARTIFACT_TYPES[req.artifact_type]
    proposed = propose_edit(artifact_cls, req.current_artifact, req.message, req.history)
    return {"proposed_artifact": proposed}


@app.post("/runs/{run_id}/interrupt/resume")
def post_interrupt_resume(run_id: str, payload: dict) -> dict:
    return run_manager.resume_run(run_id, payload)
