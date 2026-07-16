import asyncio
import json
import os
import secrets
from pathlib import Path
import mimetypes

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from server.run_manager import RunManager
from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.edit_assistant import propose_edit
from spectacle_core.models import SceneGraph, Script
from spectacle_education.lesson_plan import LessonPlan

_API_KEY_ENV = "SPECTACLE_API_KEY"


def require_api_key(
    authorization: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
) -> None:
    """Every route depends on this. CORS alone does not stop direct HTTP
    clients (curl, another host on the network) from reaching these
    endpoints, so a shared bearer token is required. `api_key` query-param
    support exists because EventSource (used by /runs/{id}/stream) cannot
    set custom request headers."""
    expected = os.environ.get(_API_KEY_ENV)
    if not expected:
        raise HTTPException(status_code=500, detail=f"{_API_KEY_ENV} is not configured")

    token = api_key
    if token is None and authorization is not None:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value

    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


app = FastAPI(dependencies=[Depends(require_api_key)])
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://localhost:\d+$",
    allow_methods=["*"],
    allow_headers=["*"],
)

_DEFAULT_ARTIFACT_ROOT = Path(__file__).resolve().parents[4] / "artifacts"

run_manager = RunManager(
    artifact_root=Path(os.environ.get("SPECTACLE_ARTIFACT_ROOT", str(_DEFAULT_ARTIFACT_ROOT))).resolve(),
    pg_conn=os.environ.get("SPECTACLE_PG_CONN", "postgresql://spectacle:spectacle@localhost:5433/spectacle"),
)


class StartRunRequest(BaseModel):
    raw_input: str | None = None
    spec: dict | None = None
    run_mode: str = "accept_edits"
    stub_llm: bool = False


@app.get("/runs")
def get_runs() -> list[dict]:
    return run_manager.list_runs()


@app.post("/runs", status_code=201)
def post_runs(req: StartRunRequest) -> dict:
    if req.raw_input is None and req.spec is None:
        raise HTTPException(status_code=400, detail="either raw_input or spec is required")
    if req.raw_input is not None and req.spec is not None:
        raise HTTPException(status_code=400, detail="provide only one of raw_input or spec")
    run_id = run_manager.start_run(req.raw_input, req.spec, req.run_mode, stub_llm=req.stub_llm)
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


@app.get("/artifacts/{content_hash}")
def get_artifact(content_hash: str) -> dict:
    store = LocalFileArtifactStore(run_manager.artifact_root)
    try:
        if not store.exists(content_hash):
            raise HTTPException(status_code=404, detail="artifact not found")
        return store.get_json(content_hash)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

@app.get("/api/artifacts/{content_hash}/{filename}")
def get_any_artifact_file(content_hash: str, filename: str):
    store = LocalFileArtifactStore(run_manager.artifact_root)
    try:
        file_path = store.file_path(content_hash, filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(str(file_path), media_type=mime_type or "application/octet-stream")


@app.post("/runs/{run_id}/simulate-crash")
def post_simulate_crash(run_id: str) -> dict:
    os._exit(1)  # pragma: no cover -- unreachable in tests, os._exit is mocked
    return {}  # pragma: no cover -- unreachable in normal operation


@app.post("/runs/{run_id}/resume")
def post_resume(run_id: str, payload: dict) -> dict:
    return run_manager.resume_run(run_id, payload)


_ARTIFACT_TYPES = {"Script": Script, "SceneGraph": SceneGraph, "LessonPlan": LessonPlan}


def _anthropic_edit_llm(artifact_type, current_artifact: dict, chat_message: str, history: list[dict]) -> dict:
    import anthropic as _anthropic

    client = _anthropic.Anthropic()
    schema = artifact_type.model_json_schema()
    system = (
        f"You are an editor for a video pipeline artifact of type {artifact_type.__name__}. "
        f"Schema: {json.dumps(schema)}. "
        "Apply the user's requested change and return ONLY the complete updated artifact as a "
        "JSON object matching the schema exactly. No prose, no markdown fences."
    )
    messages = []
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({
        "role": "user",
        "content": f"Current artifact:\n{json.dumps(current_artifact, indent=2)}\n\nRequested change: {chat_message}",
    })
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=system,
        messages=messages,
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        text = inner.rsplit("```", 1)[0].strip()
    return json.loads(text)


class ChatEditRequest(BaseModel):
    artifact_type: str
    current_artifact: dict
    message: str
    history: list[dict] = []


@app.post("/runs/{run_id}/interrupt/chat")
def post_interrupt_chat(run_id: str, req: ChatEditRequest) -> dict:
    artifact_cls = _ARTIFACT_TYPES.get(req.artifact_type)
    if artifact_cls is None:
        raise HTTPException(status_code=400, detail=f"unknown artifact_type: {req.artifact_type}")
    proposed = propose_edit(artifact_cls, req.current_artifact, req.message, req.history, llm_fn=_anthropic_edit_llm)
    return {"proposed_artifact": proposed}


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def generator():
        last_payload: str | None = None
        terminal = {"done", "error"}
        while True:
            status = run_manager.get_status(run_id)
            artifacts = await asyncio.to_thread(run_manager.list_artifacts, run_id)
            try:
                payload = json.dumps({"status": status, "artifacts": artifacts})
            except (TypeError, ValueError) as exc:
                payload = json.dumps({"status": {"status": status.get("status") if status else None}, "artifacts": artifacts, "_err": str(exc)})
            if payload != last_payload:
                last_payload = payload
                yield f"data: {payload}\n\n"
            if status and status.get("status") in terminal:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/runs/{run_id}/interrupt/resume")
def post_interrupt_resume(run_id: str, payload: dict) -> dict:
    return run_manager.resume_run(run_id, payload)
