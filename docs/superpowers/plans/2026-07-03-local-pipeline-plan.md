# Spectacle Local Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local, fully-working version of the Spectacle pipeline — a lesson spec goes in, a rendered MP4 comes out, via a LangGraph graph with a Postgres checkpointer, two human-review interrupts, an independent sympy verification gate, per-scene Remotion/Manim renderer routing, and a Next.js chat+artifacts UI — demonstrating all six architectural claims from the design spec end to end on one machine.

**Architecture:** Three Python packages (`packages/core` — engine, no domain imports; `domains/education` — the only domain pack; `apps/interview-demo/server` — FastAPI wiring) plus a Next.js frontend and a small Remotion renderer project, built bottom-up: hashing/artifact-store primitives → domain-pack protocol and education pack → LangGraph nodes → renderers/TTS → FastAPI → Next.js. GCP deployment (Cloud Run/Cloud Tasks/GCS/Cloud SQL) is **out of scope for this plan** — it's a follow-on plan once this local system works; the `ArtifactStore` and `RenderDispatcher`-shaped seams below exist specifically so that later plan doesn't require rework here.

**Tech Stack:** Python 3.11+, LangGraph (+ `langgraph-checkpoint-postgres`), pydantic v2, sympy, Manim, FastAPI + uvicorn, psycopg3, pytest; Next.js (TypeScript) + Remotion; Postgres via docker-compose; macOS `say` + ffmpeg/ffprobe for TTS.

## Global Constraints

- `packages/core` never imports from `domains/` or references education-specific vocabulary (scene type names like `"worked_example"`). It only ever sees the domain-agnostic `render_hint` field (`"layout"` | `"equation_morph"`).
- A domain pack is a plain importable Python object satisfying the `DomainPack` protocol (`spec_schema`, `structure(spec) -> ContentTree`, `verification_gates(scene) -> list[VerificationGate]`, `safety_profile`). No plugin registry, no dynamic loading.
- Every pipeline-stage artifact is a pydantic model hashed via canonical JSON (`sha256`, sorted keys), embeds its upstream hash(es) plus a `node_version` string, and is written to an `ArtifactStore` the moment it's produced (no batching until run end).
- `scene_input_hash` for a scene is computed from **only that scene's own fields** (narration, on-screen text, renderer tag, render params, expression, stated answer) — never from sibling scenes or the whole `SceneGraph` — so editing one scene never changes another scene's cache key.
- User-selectable lesson duration is 1–10 minutes, 1-minute increments, treated as a soft target (±30s tolerance), realized via the fixed scene-type menu (`intro`, `concept_explanation`, `worked_example`, `guided_practice`, `recap`) owned entirely by `domains/education`.
- Run mode (`accept_edits` default | `auto`) gates only the two human-review interrupts (after script, after scene graph). The sympy `verification_gate` is exempt from run mode and always enforced.
- TTS is per-scene (not full-script): narration is synthesized first, and its measured duration is passed into the renderer as a param, so audio and video match by construction.
- GCP deployment, Cloud Tasks, GCS, Cloud SQL, concurrent runs, multi-objective lessons, and CI/CD are explicitly out of scope for this plan.

---

## File Structure

```
packages/core/
  pyproject.toml
  src/spectacle_core/
    __init__.py
    hashing.py              # canonical_json_bytes(), content_hash()
    artifacts.py            # ArtifactStore protocol, LocalFileArtifactStore
    domain_pack.py           # DomainPack protocol, SceneStub, ContentTree, SafetyProfile, VerificationOutcome
    models.py                 # VersionedArtifact, SceneNarration, Script, SceneGraphEntry, SceneGraph,
                               # VerificationResult, NarrationClip, ScenePreview, RenderManifest, SceneFinal, FinalManifest
    renderer_routing.py        # RENDER_HINT_TO_RENDERER, choose_renderer()
    tts.py                     # TTSProvider protocol, MacSayTTSProvider
    edit_assistant.py           # propose_edit() domain-agnostic chat-edit call
    renderers/
      __init__.py
      manim_scene.py            # EquationMorphScene (Manim Scene subclass)
      manim_render.py            # render_manim()
      remotion_render.py          # render_remotion()
    nodes/
      __init__.py
      script_agent.py             # run_script_agent()
      scene_planner.py             # run_scene_planner()
      interrupts.py                 # interrupt_review()
      verification_gate.py           # run_verification_gate()
      render_scene.py                 # fan_out_scenes(), render_scene_node()
      finalize.py                      # collect_scenes_node(), mux_final_node()
    graph.py                       # GraphState, build_graph()
  tests/
    test_hashing.py
    test_artifacts.py
    test_models.py
    test_renderer_routing.py
    test_tts.py
    test_manim_render.py
    test_remotion_render.py
    test_script_agent.py
    test_scene_planner.py
    test_interrupts.py
    test_verification_gate.py
    test_render_scene.py
    test_graph_integration.py
    test_graph_kill_resume.py

domains/education/
  pyproject.toml
  src/spectacle_education/
    __init__.py               # exposes `education_pack: DomainPack` instance
    spec.py                     # EducationSpec
    scene_menu.py                 # SceneTypeDef, SCENE_MENU, budget_scenes()
    structure_agent.py             # structure()
    verification.py                  # sympy_equivalence_gate()
    safety.py                          # education_safety_profile
  tests/
    test_scene_menu.py
    test_structure_agent.py
    test_verification.py

apps/interview-demo/
  server/
    pyproject.toml
    src/server/
      __init__.py
      db.py                    # Postgres connection + artifacts metadata table DDL/queries
      run_manager.py             # RunManager: start/status/resume/simulate-crash
      main.py                      # FastAPI app + routes
    tests/
      test_db.py
      test_run_manager.py
      test_main.py
  renderer-remotion/
    package.json
    tsconfig.json
    src/
      index.ts
      Root.tsx
      LayoutScene.tsx
  web/
    package.json
    (Next.js app — scaffolded in Task 24, fleshed out in Tasks 25-26)

docker-compose.yml           # local Postgres for the checkpointer + artifacts metadata
```

---

### Task 1: Python workspace scaffolding

**Files:**
- Create: `packages/core/pyproject.toml`
- Create: `packages/core/src/spectacle_core/__init__.py`
- Create: `domains/education/pyproject.toml`
- Create: `domains/education/src/spectacle_education/__init__.py`
- Create: `apps/interview-demo/server/pyproject.toml`
- Create: `apps/interview-demo/server/src/server/__init__.py`
- Create: `pytest.ini`
- Modify: `.gitignore` (already ignores `__pycache__/`, `.venv/` — no change needed, verify only)

**Interfaces:**
- Produces: three installable Python packages (`spectacle-core`, `spectacle-education`, `spectacle-server`) importable as `spectacle_core`, `spectacle_education`, `server` once installed editable.

- [ ] **Step 1: Create `packages/core/pyproject.toml`**

```toml
[project]
name = "spectacle-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "langgraph>=0.2",
    "langgraph-checkpoint-postgres>=2.0",
    "psycopg[binary]>=3.1",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `packages/core/src/spectacle_core/__init__.py`** (empty file)

- [ ] **Step 3: Create `domains/education/pyproject.toml`**

```toml
[project]
name = "spectacle-education"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "spectacle-core",
    "sympy>=1.12",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 4: Create `domains/education/src/spectacle_education/__init__.py`** (empty file, populated in Task 8)

- [ ] **Step 5: Create `apps/interview-demo/server/pyproject.toml`**

```toml
[project]
name = "spectacle-server"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "spectacle-core",
    "spectacle-education",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "psycopg[binary]>=3.1",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 6: Create `apps/interview-demo/server/src/server/__init__.py`** (empty file)

- [ ] **Step 7: Create root `pytest.ini`**

```ini
[pytest]
testpaths =
    packages/core/tests
    domains/education/tests
    apps/interview-demo/server/tests
```

- [ ] **Step 8: Install everything editable and confirm pytest collects (no tests yet)**

Run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e packages/core -e domains/education -e apps/interview-demo/server pytest
pytest --collect-only
```
Expected: exits 0, "no tests ran" (directories exist but are empty).

- [ ] **Step 9: Commit**

```bash
git add packages/core/pyproject.toml packages/core/src \
        domains/education/pyproject.toml domains/education/src \
        apps/interview-demo/server/pyproject.toml apps/interview-demo/server/src \
        pytest.ini
git commit -m "chore: scaffold three-package Python workspace"
```

---

### Task 2: Canonical JSON hashing utility

**Files:**
- Create: `packages/core/src/spectacle_core/hashing.py`
- Test: `packages/core/tests/test_hashing.py`

**Interfaces:**
- Produces: `canonical_json_bytes(obj: dict) -> bytes`, `content_hash(obj: dict) -> str`. Every later artifact model calls `content_hash`.

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_hashing.py
from spectacle_core.hashing import canonical_json_bytes, content_hash

def test_canonical_json_is_key_order_independent():
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)

def test_canonical_json_has_no_extra_whitespace():
    assert canonical_json_bytes({"a": 1}) == b'{"a":1}'

def test_content_hash_is_deterministic():
    obj = {"x": [1, 2, 3], "y": "hello"}
    assert content_hash(obj) == content_hash(dict(obj))

def test_content_hash_differs_on_different_content():
    assert content_hash({"a": 1}) != content_hash({"a": 2})

def test_content_hash_is_64_char_hex():
    h = content_hash({"a": 1})
    assert len(h) == 64
    int(h, 16)  # raises if not hex
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_hashing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.hashing'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/hashing.py
import hashlib
import json


def canonical_json_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(obj: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_hashing.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/hashing.py packages/core/tests/test_hashing.py
git commit -m "feat(core): add canonical JSON content-hashing utility"
```

---

### Task 3: ArtifactStore + versioned artifact base

**Files:**
- Create: `packages/core/src/spectacle_core/artifacts.py`
- Test: `packages/core/tests/test_artifacts.py`
- Test: `packages/core/tests/test_models.py` (partial — `VersionedArtifact` only; rest of `models.py` fields land in Task 4)
- Create: `packages/core/src/spectacle_core/models.py` (just `VersionedArtifact` for now)

**Interfaces:**
- Consumes: `content_hash` from Task 2.
- Produces: `ArtifactStore` (Protocol: `put_json`, `get_json`, `exists`, `put_file`, `file_path`, `file_exists`), `LocalFileArtifactStore`, `VersionedArtifact` (pydantic base with `node_version: str` and `.compute_hash()`).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_artifacts.py
import pytest
from pathlib import Path
from spectacle_core.artifacts import LocalFileArtifactStore


def test_put_and_get_json_roundtrip(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    store.put_json("abc123", {"hello": "world"})
    assert store.get_json("abc123") == {"hello": "world"}


def test_exists_false_before_put_true_after(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    assert store.exists("abc123") is False
    store.put_json("abc123", {"x": 1})
    assert store.exists("abc123") is True


def test_put_file_copies_and_file_exists_reports_it(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake video bytes")
    store = LocalFileArtifactStore(tmp_path / "store")
    dest = store.put_file("scenehash1", "scene_final.mp4", src)
    assert dest.exists()
    assert dest.read_bytes() == b"fake video bytes"
    assert store.file_exists("scenehash1", "scene_final.mp4") is True
    assert store.file_exists("scenehash1", "nope.mp4") is False


def test_file_path_returns_expected_location(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    assert store.file_path("h1", "final.mp4") == tmp_path / "h1" / "final.mp4"
```

```python
# packages/core/tests/test_models.py
from spectacle_core.models import VersionedArtifact


class Dummy(VersionedArtifact):
    text: str


def test_compute_hash_stable_for_same_content():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@1", text="hello")
    assert a.compute_hash() == b.compute_hash()


def test_compute_hash_changes_with_node_version_even_if_content_same():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@2", text="hello")
    assert a.compute_hash() != b.compute_hash()


def test_compute_hash_changes_with_content():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@1", text="goodbye")
    assert a.compute_hash() != b.compute_hash()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_artifacts.py packages/core/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError` for both `spectacle_core.artifacts` and `spectacle_core.models`

- [ ] **Step 3: Implement `models.py` (base only)**

```python
# packages/core/src/spectacle_core/models.py
from pydantic import BaseModel

from spectacle_core.hashing import content_hash


class VersionedArtifact(BaseModel):
    node_version: str

    def compute_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))
```

- [ ] **Step 4: Implement `artifacts.py`**

```python
# packages/core/src/spectacle_core/artifacts.py
import json
import shutil
from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def put_json(self, content_hash: str, data: dict) -> None: ...
    def get_json(self, content_hash: str) -> dict: ...
    def exists(self, content_hash: str) -> bool: ...
    def put_file(self, content_hash: str, filename: str, src_path: Path) -> Path: ...
    def file_path(self, content_hash: str, filename: str) -> Path: ...
    def file_exists(self, content_hash: str, filename: str) -> bool: ...


class LocalFileArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, content_hash: str) -> Path:
        d = self.root / content_hash
        d.mkdir(parents=True, exist_ok=True)
        return d

    def put_json(self, content_hash: str, data: dict) -> None:
        (self._dir(content_hash) / "artifact.json").write_text(json.dumps(data, indent=2))

    def get_json(self, content_hash: str) -> dict:
        return json.loads((self.root / content_hash / "artifact.json").read_text())

    def exists(self, content_hash: str) -> bool:
        return (self.root / content_hash / "artifact.json").exists()

    def put_file(self, content_hash: str, filename: str, src_path: Path) -> Path:
        dest = self._dir(content_hash) / filename
        shutil.copyfile(src_path, dest)
        return dest

    def file_path(self, content_hash: str, filename: str) -> Path:
        return self.root / content_hash / filename

    def file_exists(self, content_hash: str, filename: str) -> bool:
        return self.file_path(content_hash, filename).exists()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_artifacts.py packages/core/tests/test_models.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/spectacle_core/artifacts.py packages/core/src/spectacle_core/models.py \
        packages/core/tests/test_artifacts.py packages/core/tests/test_models.py
git commit -m "feat(core): add ArtifactStore and VersionedArtifact base"
```

---

### Task 4: Domain-pack protocol & shared content models

**Files:**
- Create: `packages/core/src/spectacle_core/domain_pack.py`
- Modify: `packages/core/src/spectacle_core/models.py` (add `SceneNarration`, `Script`, `SceneGraphEntry`, `SceneGraph`, `VerificationResult`, `NarrationClip`, `ScenePreview`, `RenderManifest`, `SceneFinal`, `FinalManifest`)
- Test: `packages/core/tests/test_models.py` (append)
- Test: `packages/core/tests/test_domain_pack.py`

**Interfaces:**
- Consumes: `VersionedArtifact`, `content_hash` (Tasks 2-3).
- Produces: `SafetyProfile`, `SceneStub`, `ContentTree`, `VerificationOutcome`, `VerificationGate` (Protocol), `DomainPack` (Protocol) — imported by `domains/education` in Tasks 6-9. `SceneGraphEntry.scene_input_hash()` — the mechanism behind claim #6, consumed by Task 15/17.

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_domain_pack.py
from spectacle_core.domain_pack import ContentTree, SceneStub


def test_scene_stub_defaults_expression_to_none():
    stub = SceneStub(
        scene_id="intro_1",
        render_hint="layout",
        content_hint="say hello",
        target_duration_s=20.0,
        verify=False,
    )
    assert stub.expression is None


def test_content_tree_holds_ordered_scenes():
    stubs = [
        SceneStub(scene_id="intro_1", render_hint="layout", content_hint="hi",
                   target_duration_s=20.0, verify=False),
        SceneStub(scene_id="worked_example_1", render_hint="equation_morph",
                   content_hint="show 3/4+1/8", target_duration_s=45.0, verify=True,
                   expression="3/4 + 1/8"),
    ]
    tree = ContentTree(spec_hash="deadbeef", scenes=stubs)
    assert [s.scene_id for s in tree.scenes] == ["intro_1", "worked_example_1"]
```

Append to `packages/core/tests/test_models.py`:

```python
from spectacle_core.models import SceneGraphEntry


def test_scene_graph_entry_hash_depends_only_on_own_fields():
    a = SceneGraphEntry(
        scene_id="intro_1", renderer="remotion", narration_text="hi",
        on_screen_text="Hi!", target_duration_s=20.0, verify=False,
    )
    b = SceneGraphEntry(
        scene_id="intro_1", renderer="remotion", narration_text="hi",
        on_screen_text="Hi!", target_duration_s=20.0, verify=False,
    )
    assert a.scene_input_hash() == b.scene_input_hash()


def test_scene_graph_entry_hash_changes_when_renderer_tag_changes():
    base = dict(
        scene_id="worked_example_1", narration_text="three quarters plus one eighth",
        on_screen_text="3/4 + 1/8", target_duration_s=45.0, verify=True,
        expression="3/4 + 1/8", stated_answer="7/8",
    )
    a = SceneGraphEntry(renderer="manim", **base)
    b = SceneGraphEntry(renderer="remotion", **base)
    assert a.scene_input_hash() != b.scene_input_hash()


def test_scene_graph_entry_hash_unaffected_by_scene_id():
    # scene_id is identity, not content -- changing it must not change the
    # cache key (two scenes with identical content but different ids should
    # still be independently cacheable by their content, but this test just
    # pins that scene_id itself is excluded from the hash inputs).
    a = SceneGraphEntry(scene_id="a", renderer="remotion", narration_text="hi",
                          on_screen_text="Hi!", target_duration_s=20.0, verify=False)
    b = SceneGraphEntry(scene_id="b", renderer="remotion", narration_text="hi",
                          on_screen_text="Hi!", target_duration_s=20.0, verify=False)
    assert a.scene_input_hash() == b.scene_input_hash()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_domain_pack.py packages/core/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.domain_pack'` and `ImportError: cannot import name 'SceneGraphEntry'`

- [ ] **Step 3: Implement `domain_pack.py`**

```python
# packages/core/src/spectacle_core/domain_pack.py
from typing import Literal, Protocol

from pydantic import BaseModel


class SafetyProfile(BaseModel):
    disallowed_topics: list[str]
    age_rating: str


class SceneStub(BaseModel):
    scene_id: str
    render_hint: Literal["layout", "equation_morph"]
    content_hint: str
    target_duration_s: float
    verify: bool
    expression: str | None = None


class ContentTree(BaseModel):
    spec_hash: str
    scenes: list[SceneStub]
    schema_version: str = "1"


class VerificationOutcome(BaseModel):
    passed: bool
    detail: str


class VerificationGate(Protocol):
    def __call__(self, scene: "SceneGraphEntry") -> VerificationOutcome: ...


class DomainPack(Protocol):
    spec_schema: type[BaseModel]

    def structure(self, spec: BaseModel) -> ContentTree: ...

    def verification_gates(self, scene: "SceneGraphEntry") -> list[VerificationGate]: ...

    safety_profile: SafetyProfile


# Imported here only for the type hint above; avoids a circular import at
# module load time since models.py does not import domain_pack.py.
from spectacle_core.models import SceneGraphEntry  # noqa: E402
```

- [ ] **Step 4: Add the remaining models to `models.py`**

```python
# packages/core/src/spectacle_core/models.py (append)
from typing import Literal

from spectacle_core.hashing import content_hash  # already imported above


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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_domain_pack.py packages/core/tests/test_models.py -v`
Expected: 8 passed (2 new domain_pack tests + 6 model tests including the 3 new hash ones)

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/spectacle_core/domain_pack.py packages/core/src/spectacle_core/models.py \
        packages/core/tests/test_domain_pack.py packages/core/tests/test_models.py
git commit -m "feat(core): add DomainPack protocol and full artifact model chain"
```

---

### Task 5: Renderer routing table

**Files:**
- Create: `packages/core/src/spectacle_core/renderer_routing.py`
- Test: `packages/core/tests/test_renderer_routing.py`

**Interfaces:**
- Produces: `RENDER_HINT_TO_RENDERER: dict[str, Literal["remotion", "manim"]]`, `choose_renderer(render_hint: str) -> Literal["remotion", "manim"]`. Consumed by Task 12 (`scene_planner`).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_renderer_routing.py
import pytest
from spectacle_core.renderer_routing import choose_renderer


def test_layout_routes_to_remotion():
    assert choose_renderer("layout") == "remotion"


def test_equation_morph_routes_to_manim():
    assert choose_renderer("equation_morph") == "manim"


def test_unknown_hint_raises_value_error():
    with pytest.raises(ValueError, match="no renderer mapped"):
        choose_renderer("something_new")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_renderer_routing.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/renderer_routing.py
from typing import Literal

RENDER_HINT_TO_RENDERER: dict[str, Literal["remotion", "manim"]] = {
    "layout": "remotion",
    "equation_morph": "manim",
}


def choose_renderer(render_hint: str) -> Literal["remotion", "manim"]:
    try:
        return RENDER_HINT_TO_RENDERER[render_hint]
    except KeyError:
        raise ValueError(f"no renderer mapped for render_hint={render_hint!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_renderer_routing.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/renderer_routing.py packages/core/tests/test_renderer_routing.py
git commit -m "feat(core): add render_hint -> renderer routing table"
```

---

### Task 6: EducationSpec + scene-type menu constants

**Files:**
- Create: `domains/education/src/spectacle_education/spec.py`
- Create: `domains/education/src/spectacle_education/scene_menu.py` (constants only — `budget_scenes` lands in Task 7)
- Test: `domains/education/tests/test_scene_menu.py` (constants only)

**Interfaces:**
- Produces: `EducationSpec` (pydantic model), `SceneTypeDef`, `SCENE_MENU: list[SceneTypeDef]`. Consumed by Task 7 (`budget_scenes`) and Task 8 (`structure`).

- [ ] **Step 1: Write the failing test**

```python
# domains/education/tests/test_scene_menu.py
from spectacle_education.scene_menu import SCENE_MENU


def test_scene_menu_has_five_fixed_types():
    names = [d.name for d in SCENE_MENU]
    assert names == [
        "intro", "concept_explanation", "worked_example",
        "guided_practice", "recap",
    ]


def test_only_equation_morph_types_are_verified():
    verified = {d.name for d in SCENE_MENU if d.verify}
    assert verified == {"worked_example", "guided_practice"}


def test_only_intro_and_recap_are_non_repeatable():
    non_repeatable = {d.name for d in SCENE_MENU if not d.repeatable}
    assert non_repeatable == {"intro", "worked_example", "recap"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest domains/education/tests/test_scene_menu.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_education.scene_menu'`

- [ ] **Step 3: Implement `spec.py`**

```python
# domains/education/src/spectacle_education/spec.py
from pydantic import BaseModel, Field


class EducationSpec(BaseModel):
    learning_objective: str
    worked_example_expression: str
    target_duration_minutes: int = Field(ge=1, le=10)
    audience: str
```

- [ ] **Step 4: Implement `scene_menu.py` (constants)**

```python
# domains/education/src/spectacle_education/scene_menu.py
from typing import Literal

from pydantic import BaseModel


class SceneTypeDef(BaseModel):
    name: str
    render_hint: Literal["layout", "equation_morph"]
    verify: bool
    duration_s: float
    repeatable: bool


SCENE_MENU: list[SceneTypeDef] = [
    SceneTypeDef(name="intro", render_hint="layout", verify=False,
                 duration_s=20.0, repeatable=False),
    SceneTypeDef(name="concept_explanation", render_hint="layout", verify=False,
                 duration_s=45.0, repeatable=True),
    SceneTypeDef(name="worked_example", render_hint="equation_morph", verify=True,
                 duration_s=45.0, repeatable=False),
    SceneTypeDef(name="guided_practice", render_hint="equation_morph", verify=True,
                 duration_s=40.0, repeatable=True),
    SceneTypeDef(name="recap", render_hint="layout", verify=False,
                 duration_s=20.0, repeatable=False),
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest domains/education/tests/test_scene_menu.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add domains/education/src/spectacle_education/spec.py \
        domains/education/src/spectacle_education/scene_menu.py \
        domains/education/tests/test_scene_menu.py
git commit -m "feat(education): add EducationSpec and fixed scene-type menu"
```

---

### Task 7: Duration budgeting (`budget_scenes`)

**Files:**
- Modify: `domains/education/src/spectacle_education/scene_menu.py` (add `budget_scenes`)
- Test: `domains/education/tests/test_scene_menu.py` (append)

**Interfaces:**
- Consumes: `EducationSpec` (Task 6), `SceneStub` (Task 4, `spectacle_core.domain_pack`).
- Produces: `budget_scenes(spec: EducationSpec) -> list[SceneStub]`. Consumed by Task 8 (`structure`).

- [ ] **Step 1: Write the failing tests**

Append to `domains/education/tests/test_scene_menu.py`:

```python
from spectacle_education.scene_menu import budget_scenes
from spectacle_education.spec import EducationSpec


def _spec(minutes: int) -> EducationSpec:
    return EducationSpec(
        learning_objective="add fractions with unlike denominators",
        worked_example_expression="3/4 + 1/8",
        target_duration_minutes=minutes,
        audience="6th grade",
    )


def _type_names(scenes) -> list[str]:
    return [s.scene_id.rsplit("_", 1)[0] for s in scenes]


def test_one_minute_lesson_has_only_the_three_mandatory_scenes():
    scenes = budget_scenes(_spec(1))
    assert _type_names(scenes) == ["intro", "worked_example", "recap"]


def test_ten_minute_lesson_stays_in_pedagogical_order_and_adds_fillers():
    scenes = budget_scenes(_spec(10))
    names = _type_names(scenes)
    assert names[0] == "intro"
    assert names[-1] == "recap"
    assert "worked_example" in names
    assert names.count("concept_explanation") >= 1
    assert names.count("guided_practice") >= 1
    # pedagogical order: all concept_explanations before worked_example,
    # all guided_practice after it, recap last.
    we_index = names.index("worked_example")
    assert all(n == "concept_explanation" for n in names[1:we_index])
    assert all(n == "guided_practice" for n in names[we_index + 1:-1])


def test_ten_minute_lesson_total_duration_within_tolerance():
    scenes = budget_scenes(_spec(10))
    total_s = sum(s.target_duration_s for s in scenes)
    target_s = 10 * 60
    assert abs(total_s - target_s) <= 60


def test_only_equation_morph_scenes_carry_verify_true():
    scenes = budget_scenes(_spec(10))
    for s in scenes:
        name = s.scene_id.rsplit("_", 1)[0]
        if name in ("worked_example", "guided_practice"):
            assert s.verify is True
            assert s.render_hint == "equation_morph"
        else:
            assert s.verify is False
            assert s.render_hint == "layout"


def test_worked_example_expression_is_none_until_structure_fills_it_in():
    # budget_scenes is deterministic and domain-agnostic about *which*
    # expression to use -- structure() (Task 8) fills expression in.
    scenes = budget_scenes(_spec(5))
    for s in scenes:
        assert s.expression is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest domains/education/tests/test_scene_menu.py -v`
Expected: FAIL with `ImportError: cannot import name 'budget_scenes'`

- [ ] **Step 3: Implement `budget_scenes`**

```python
# domains/education/src/spectacle_education/scene_menu.py (append)
from spectacle_core.domain_pack import SceneStub
from spectacle_education.spec import EducationSpec

_TOLERANCE_S = 30.0
_PEDAGOGICAL_ORDER = {
    "intro": 0,
    "concept_explanation": 1,
    "worked_example": 2,
    "guided_practice": 3,
    "recap": 4,
}


def budget_scenes(spec: EducationSpec) -> list[SceneStub]:
    """Deterministic budgeting: pick a sequence and count of scenes from
    SCENE_MENU whose total duration approximates the requested target
    (soft target, +/- _TOLERANCE_S), rather than letting an LLM invent
    open-ended content depth. The three mandatory scenes (intro,
    worked_example, recap) always appear; concept_explanation and
    guided_practice are added alternately to fill remaining budget."""
    menu = {d.name: d for d in SCENE_MENU}
    target_s = spec.target_duration_minutes * 60
    counters: dict[str, int] = {}
    scenes: list[SceneStub] = []

    def add(name: str) -> float:
        defn = menu[name]
        counters[name] = counters.get(name, 0) + 1
        scenes.append(SceneStub(
            scene_id=f"{name}_{counters[name]}",
            render_hint=defn.render_hint,
            content_hint=f"{name} scene for: {spec.learning_objective}",
            target_duration_s=defn.duration_s,
            verify=defn.verify,
        ))
        return defn.duration_s

    used_s = add("intro") + add("worked_example") + add("recap")

    fillers = ["concept_explanation", "guided_practice"]
    filler_idx = 0
    while target_s - used_s > _TOLERANCE_S:
        name = fillers[filler_idx % 2]
        used_s += add(name)
        filler_idx += 1

    scenes.sort(key=lambda s: _PEDAGOGICAL_ORDER[s.scene_id.rsplit("_", 1)[0]])
    return scenes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest domains/education/tests/test_scene_menu.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add domains/education/src/spectacle_education/scene_menu.py domains/education/tests/test_scene_menu.py
git commit -m "feat(education): add deterministic duration budgeting (budget_scenes)"
```

---

### Task 8: `structure()`, `verification_gates()`, `safety_profile`, and the `DomainPack` instance

**Files:**
- Create: `domains/education/src/spectacle_education/structure_agent.py`
- Create: `domains/education/src/spectacle_education/verification.py` (stub gate function only — real sympy logic lands in Task 9)
- Create: `domains/education/src/spectacle_education/safety.py`
- Modify: `domains/education/src/spectacle_education/__init__.py`
- Test: `domains/education/tests/test_structure_agent.py`

**Interfaces:**
- Consumes: `budget_scenes` (Task 7), `ContentTree`/`SceneStub` (Task 4), `DomainPack`/`SafetyProfile` (Task 4).
- Produces: `structure(spec, guided_practice_expression_fn=..., content_hint_fn=...) -> ContentTree`, `education_pack: DomainPack` (the module-level instance apps import). `verification_gates` here is a thin wrapper — real gate logic is Task 9.

- [ ] **Step 1: Write the failing tests**

```python
# domains/education/tests/test_structure_agent.py
from spectacle_education.spec import EducationSpec
from spectacle_education.structure_agent import structure


def _spec() -> EducationSpec:
    return EducationSpec(
        learning_objective="add fractions with unlike denominators",
        worked_example_expression="3/4 + 1/8",
        target_duration_minutes=5,
        audience="6th grade",
    )


def test_structure_sets_spec_hash_deterministically():
    from spectacle_core.hashing import content_hash
    spec = _spec()
    tree = structure(spec)
    assert tree.spec_hash == content_hash(spec.model_dump(mode="json"))


def test_worked_example_gets_the_spec_expression():
    tree = structure(_spec())
    we = next(s for s in tree.scenes if s.scene_id.startswith("worked_example"))
    assert we.expression == "3/4 + 1/8"


def test_guided_practice_gets_an_llm_supplied_expression():
    def fake_guided_practice_expression(spec):
        return "1/2 + 1/4"

    tree = structure(_spec(), guided_practice_expression_fn=fake_guided_practice_expression)
    practice_scenes = [s for s in tree.scenes if s.scene_id.startswith("guided_practice")]
    assert practice_scenes, "5-minute lesson should include at least one guided_practice scene"
    assert all(s.expression == "1/2 + 1/4" for s in practice_scenes)


def test_content_hint_fn_is_used_to_enrich_every_scene():
    def fake_content_hint(spec, stub):
        return f"FAKE HINT for {stub.scene_id}"

    tree = structure(_spec(), content_hint_fn=fake_content_hint)
    for stub in tree.scenes:
        assert stub.content_hint == f"FAKE HINT for {stub.scene_id}"


def test_layout_scenes_never_get_an_expression():
    tree = structure(_spec())
    for stub in tree.scenes:
        if stub.render_hint == "layout":
            assert stub.expression is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest domains/education/tests/test_structure_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_education.structure_agent'`

- [ ] **Step 3: Implement `structure_agent.py`**

```python
# domains/education/src/spectacle_education/structure_agent.py
from typing import Callable

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_education.scene_menu import budget_scenes
from spectacle_education.spec import EducationSpec

ContentHintFn = Callable[[EducationSpec, SceneStub], str]
GuidedPracticeExpressionFn = Callable[[EducationSpec], str]


def default_content_hint_llm(spec: EducationSpec, stub: SceneStub) -> str:
    """Real implementation calls an LLM to write a one-line pedagogical
    angle for this scene, given the lesson's learning objective. Kept as
    an injectable seam so callers (and tests) can swap it out."""
    raise NotImplementedError("wire up a real LLM client here")


def default_guided_practice_expression_llm(spec: EducationSpec) -> str:
    """Real implementation calls an LLM to pick an analogous, easier
    expression exercising the same skill as spec.worked_example_expression."""
    raise NotImplementedError("wire up a real LLM client here")


def structure(
    spec: EducationSpec,
    guided_practice_expression_fn: GuidedPracticeExpressionFn = default_guided_practice_expression_llm,
    content_hint_fn: ContentHintFn = default_content_hint_llm,
) -> ContentTree:
    spec_hash = content_hash(spec.model_dump(mode="json"))
    stubs = budget_scenes(spec)

    guided_practice_expression: str | None = None
    enriched: list[SceneStub] = []
    for stub in stubs:
        name = stub.scene_id.rsplit("_", 1)[0]
        expression = None
        if name == "worked_example":
            expression = spec.worked_example_expression
        elif name == "guided_practice":
            if guided_practice_expression is None:
                guided_practice_expression = guided_practice_expression_fn(spec)
            expression = guided_practice_expression
        enriched.append(stub.model_copy(update={
            "content_hint": content_hint_fn(spec, stub),
            "expression": expression,
        }))

    return ContentTree(spec_hash=spec_hash, scenes=enriched)
```

- [ ] **Step 4: Implement `verification.py` (stub), `safety.py`, and `__init__.py`**

```python
# domains/education/src/spectacle_education/verification.py
from spectacle_core.domain_pack import VerificationGate, VerificationOutcome
from spectacle_core.models import SceneGraphEntry


def sympy_equivalence_gate(scene: SceneGraphEntry) -> VerificationOutcome:
    raise NotImplementedError("implemented in Task 9")


def verification_gates(scene: SceneGraphEntry) -> list[VerificationGate]:
    if scene.verify:
        return [sympy_equivalence_gate]
    return []
```

```python
# domains/education/src/spectacle_education/safety.py
from spectacle_core.domain_pack import SafetyProfile

education_safety_profile = SafetyProfile(
    disallowed_topics=["violence", "explicit content"],
    age_rating="general",
)
```

```python
# domains/education/src/spectacle_education/__init__.py
from spectacle_education.safety import education_safety_profile
from spectacle_education.spec import EducationSpec
from spectacle_education.structure_agent import structure
from spectacle_education.verification import verification_gates


class _EducationPack:
    spec_schema = EducationSpec
    structure = staticmethod(structure)
    verification_gates = staticmethod(verification_gates)
    safety_profile = education_safety_profile


education_pack = _EducationPack()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest domains/education/tests/test_structure_agent.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add domains/education/src/spectacle_education/structure_agent.py \
        domains/education/src/spectacle_education/verification.py \
        domains/education/src/spectacle_education/safety.py \
        domains/education/src/spectacle_education/__init__.py \
        domains/education/tests/test_structure_agent.py
git commit -m "feat(education): add structure(), safety profile, and DomainPack instance"
```

---

### Task 9: sympy equivalence verification gate

**Files:**
- Modify: `domains/education/src/spectacle_education/verification.py`
- Test: `domains/education/tests/test_verification.py`

**Interfaces:**
- Consumes: `SceneGraphEntry` (Task 4).
- Produces: real `sympy_equivalence_gate(scene: SceneGraphEntry) -> VerificationOutcome`. Consumed by Task 14 (`verification_gate` node).

- [ ] **Step 1: Write the failing tests**

```python
# domains/education/tests/test_verification.py
from spectacle_core.models import SceneGraphEntry
from spectacle_education.verification import sympy_equivalence_gate


def _scene(expression: str, stated_answer: str | None) -> SceneGraphEntry:
    return SceneGraphEntry(
        scene_id="worked_example_1", renderer="manim",
        narration_text="...", on_screen_text="...",
        target_duration_s=45.0, verify=True,
        expression=expression, stated_answer=stated_answer,
    )


def test_matching_answer_passes():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", "7/8"))
    assert outcome.passed is True


def test_mismatching_answer_fails():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", "1/2"))
    assert outcome.passed is False
    assert "7/8" in outcome.detail


def test_equivalent_but_differently_formatted_answer_passes():
    outcome = sympy_equivalence_gate(_scene("1/2 + 1/2", "1"))
    assert outcome.passed is True


def test_malformed_expression_fails_without_raising():
    outcome = sympy_equivalence_gate(_scene("3/4 + )( garbage", "7/8"))
    assert outcome.passed is False
    assert "could not parse" in outcome.detail


def test_missing_stated_answer_fails_without_raising():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", None))
    assert outcome.passed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest domains/education/tests/test_verification.py -v`
Expected: FAIL with `NotImplementedError: implemented in Task 9`

- [ ] **Step 3: Implement**

```python
# domains/education/src/spectacle_education/verification.py
import sympy
from sympy import SympifyError

from spectacle_core.domain_pack import VerificationGate, VerificationOutcome
from spectacle_core.models import SceneGraphEntry


def sympy_equivalence_gate(scene: SceneGraphEntry) -> VerificationOutcome:
    if scene.expression is None or scene.stated_answer is None:
        return VerificationOutcome(
            passed=False,
            detail="missing expression or stated_answer for a verified scene",
        )
    try:
        expected = sympy.simplify(sympy.sympify(scene.expression))
        stated = sympy.simplify(sympy.sympify(scene.stated_answer))
    except (SympifyError, TypeError) as exc:
        return VerificationOutcome(passed=False, detail=f"could not parse expression: {exc}")

    passed = sympy.simplify(expected - stated) == 0
    detail = "matches" if passed else f"expected {expected}, script stated {stated}"
    return VerificationOutcome(passed=passed, detail=detail)


def verification_gates(scene: SceneGraphEntry) -> list[VerificationGate]:
    if scene.verify:
        return [sympy_equivalence_gate]
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest domains/education/tests/test_verification.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add domains/education/src/spectacle_education/verification.py domains/education/tests/test_verification.py
git commit -m "feat(education): implement sympy equivalence verification gate"
```

---

### Task 10: Script agent node

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/__init__.py` (empty)
- Create: `packages/core/src/spectacle_core/nodes/script_agent.py`
- Test: `packages/core/tests/test_script_agent.py`

**Interfaces:**
- Consumes: `ContentTree`, `SceneStub` (Task 4), `Script`, `SceneNarration` (Task 4), `content_hash` (Task 2).
- Produces: `run_script_agent(tree: ContentTree, llm_fn=default_script_llm) -> Script`. Consumed by Task 17 (`graph.py`).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_script_agent.py
from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.nodes.script_agent import ScriptLLMResponse, run_script_agent


def _tree() -> ContentTree:
    stubs = [
        SceneStub(scene_id="intro_1", render_hint="layout", content_hint="say hi",
                   target_duration_s=20.0, verify=False),
        SceneStub(scene_id="worked_example_1", render_hint="equation_morph",
                   content_hint="show 3/4+1/8", target_duration_s=45.0, verify=True,
                   expression="3/4 + 1/8"),
    ]
    return ContentTree(spec_hash="deadbeef", scenes=stubs)


def _fake_llm(stub: SceneStub) -> ScriptLLMResponse:
    if stub.expression is not None:
        return ScriptLLMResponse(
            narration_text=f"narration for {stub.scene_id}",
            on_screen_text=f"on-screen for {stub.scene_id}",
            stated_answer="7/8",
        )
    return ScriptLLMResponse(
        narration_text=f"narration for {stub.scene_id}",
        on_screen_text=f"on-screen for {stub.scene_id}",
    )


def test_script_has_one_scene_narration_per_stub_in_order():
    script = run_script_agent(_tree(), llm_fn=_fake_llm)
    assert [s.scene_id for s in script.scenes] == ["intro_1", "worked_example_1"]


def test_script_carries_forward_expression_and_verify():
    script = run_script_agent(_tree(), llm_fn=_fake_llm)
    we = script.scenes[1]
    assert we.expression == "3/4 + 1/8"
    assert we.verify is True
    assert we.stated_answer == "7/8"


def test_layout_scene_has_no_stated_answer():
    script = run_script_agent(_tree(), llm_fn=_fake_llm)
    intro = script.scenes[0]
    assert intro.stated_answer is None


def test_script_tree_hash_matches_content_hash_of_tree():
    from spectacle_core.hashing import content_hash
    tree = _tree()
    script = run_script_agent(tree, llm_fn=_fake_llm)
    assert script.tree_hash == content_hash(tree.model_dump(mode="json"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_script_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.nodes'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/nodes/script_agent.py
from typing import Callable

from pydantic import BaseModel

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneNarration, Script


class ScriptLLMResponse(BaseModel):
    narration_text: str
    on_screen_text: str
    stated_answer: str | None = None


ScriptLLMFn = Callable[[SceneStub], ScriptLLMResponse]


def default_script_llm(stub: SceneStub) -> ScriptLLMResponse:
    """Real implementation calls an LLM to write narration/on-screen text
    for this scene, and (for verified scenes) the script's claimed final
    answer -- the claim sympy independently checks downstream."""
    raise NotImplementedError("wire up a real LLM client here")


def run_script_agent(tree: ContentTree, llm_fn: ScriptLLMFn = default_script_llm) -> Script:
    scenes = []
    for stub in tree.scenes:
        resp = llm_fn(stub)
        scenes.append(SceneNarration(
            scene_id=stub.scene_id,
            render_hint=stub.render_hint,
            narration_text=resp.narration_text,
            on_screen_text=resp.on_screen_text,
            target_duration_s=stub.target_duration_s,
            verify=stub.verify,
            expression=stub.expression,
            stated_answer=resp.stated_answer,
        ))
    tree_hash = content_hash(tree.model_dump(mode="json"))
    return Script(tree_hash=tree_hash, scenes=scenes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_script_agent.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/nodes/__init__.py packages/core/src/spectacle_core/nodes/script_agent.py \
        packages/core/tests/test_script_agent.py
git commit -m "feat(core): add script_agent node"
```

---

### Task 11: Interrupt review helper (used for both Interrupt A and B)

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/interrupts.py`
- Test: `packages/core/tests/test_interrupts.py`

**Interfaces:**
- Consumes: LangGraph's `interrupt()` (from `langgraph.types`).
- Produces: `interrupt_review(artifact: BaseModel, artifact_cls: type[BaseModel], run_mode: str) -> BaseModel`. Consumed by Task 17 (`graph.py`, wired as the Interrupt A / Interrupt B nodes).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_interrupts.py
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from spectacle_core.nodes.interrupts import interrupt_review


class Dummy(BaseModel):
    text: str


def test_auto_mode_never_calls_interrupt_and_returns_artifact_unchanged():
    with patch("spectacle_core.nodes.interrupts.interrupt") as mock_interrupt:
        result = interrupt_review(Dummy(text="hello"), Dummy, run_mode="auto")
    mock_interrupt.assert_not_called()
    assert result == Dummy(text="hello")


def test_accept_edits_mode_approve_returns_artifact_unchanged():
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value={"action": "approve"}):
        result = interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")
    assert result == Dummy(text="hello")


def test_accept_edits_mode_edit_returns_new_validated_artifact():
    edited_payload = {"action": "edit", "artifact": {"text": "goodbye"}}
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value=edited_payload):
        result = interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")
    assert result == Dummy(text="goodbye")


def test_unknown_action_raises():
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value={"action": "nonsense"}):
        with pytest.raises(ValueError, match="unknown interrupt action"):
            interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_interrupts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.nodes.interrupts'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/nodes/interrupts.py
from typing import Literal

from langgraph.types import interrupt
from pydantic import BaseModel


def interrupt_review(
    artifact: BaseModel,
    artifact_cls: type[BaseModel],
    run_mode: Literal["accept_edits", "auto"],
) -> BaseModel:
    """Pause for human review unless run_mode == 'auto'. Returns the
    (possibly edited) artifact to continue the graph with."""
    if run_mode == "auto":
        return artifact

    decision = interrupt({"artifact": artifact.model_dump(mode="json")})

    if decision["action"] == "approve":
        return artifact
    if decision["action"] == "edit":
        return artifact_cls.model_validate(decision["artifact"])
    raise ValueError(f"unknown interrupt action: {decision['action']!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_interrupts.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/nodes/interrupts.py packages/core/tests/test_interrupts.py
git commit -m "feat(core): add run-mode-aware interrupt_review helper"
```

---

### Task 12: Scene planner node

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/scene_planner.py`
- Test: `packages/core/tests/test_scene_planner.py`

**Interfaces:**
- Consumes: `Script`, `SceneNarration` (Task 4/10), `choose_renderer` (Task 5), `content_hash` (Task 2).
- Produces: `run_scene_planner(script: Script) -> SceneGraph`. Consumed by Task 17.

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_scene_planner.py
from spectacle_core.models import SceneNarration, Script
from spectacle_core.nodes.scene_planner import run_scene_planner


def _script() -> Script:
    return Script(
        tree_hash="deadbeef",
        scenes=[
            SceneNarration(scene_id="intro_1", render_hint="layout",
                             narration_text="hi", on_screen_text="Hi!",
                             target_duration_s=20.0, verify=False),
            SceneNarration(scene_id="worked_example_1", render_hint="equation_morph",
                             narration_text="three quarters plus one eighth",
                             on_screen_text="3/4 + 1/8", target_duration_s=45.0,
                             verify=True, expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_scene_graph_has_one_entry_per_script_scene_in_order():
    graph = run_scene_planner(_script())
    assert [s.scene_id for s in graph.scenes] == ["intro_1", "worked_example_1"]


def test_layout_scene_routed_to_remotion_and_equation_morph_to_manim():
    graph = run_scene_planner(_script())
    intro, worked = graph.scenes
    assert intro.renderer == "remotion"
    assert worked.renderer == "manim"


def test_expression_and_stated_answer_carried_forward():
    graph = run_scene_planner(_script())
    worked = graph.scenes[1]
    assert worked.expression == "3/4 + 1/8"
    assert worked.stated_answer == "7/8"


def test_script_hash_matches_content_hash_of_script():
    from spectacle_core.hashing import content_hash
    script = _script()
    graph = run_scene_planner(script)
    assert graph.script_hash == content_hash(script.model_dump(mode="json"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_scene_planner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.nodes.scene_planner'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/nodes/scene_planner.py
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneGraph, SceneGraphEntry, Script
from spectacle_core.renderer_routing import choose_renderer


def run_scene_planner(script: Script) -> SceneGraph:
    entries = [
        SceneGraphEntry(
            scene_id=s.scene_id,
            renderer=choose_renderer(s.render_hint),
            narration_text=s.narration_text,
            on_screen_text=s.on_screen_text,
            target_duration_s=s.target_duration_s,
            verify=s.verify,
            expression=s.expression,
            stated_answer=s.stated_answer,
        )
        for s in script.scenes
    ]
    script_hash = content_hash(script.model_dump(mode="json"))
    return SceneGraph(script_hash=script_hash, scenes=entries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_scene_planner.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/nodes/scene_planner.py packages/core/tests/test_scene_planner.py
git commit -m "feat(core): add scene_planner node (render_hint -> renderer tagging)"
```

---

### Task 13: Interrupt B — prove selective per-scene hash invalidation (claim #6)

**Files:**
- Test: `packages/core/tests/test_interrupts.py` (append — this is the concrete proof of claim #6, still using the same `interrupt_review` helper from Task 11)

**Interfaces:**
- Consumes: `interrupt_review` (Task 11), `SceneGraph`/`SceneGraphEntry` (Task 4).
- Produces: nothing new — this task is a targeted test proving an already-built mechanism does what claim #6 requires, using the actual production types instead of the `Dummy` model from Task 11.

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/test_interrupts.py`:

```python
from spectacle_core.models import SceneGraph, SceneGraphEntry


def _scene_graph() -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="three quarters plus one eighth",
                              on_screen_text="3/4 + 1/8", target_duration_s=45.0,
                              verify=True, expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_editing_one_scenes_renderer_tag_only_changes_that_scenes_hash():
    original = _scene_graph()
    before_hashes = {s.scene_id: s.scene_input_hash() for s in original.scenes}

    edited_payload = original.model_dump(mode="json")
    edited_payload["scenes"][0]["renderer"] = "manim"  # flip intro_1's tag
    decision = {"action": "edit", "artifact": edited_payload}

    with patch("spectacle_core.nodes.interrupts.interrupt", return_value=decision):
        result = interrupt_review(original, SceneGraph, run_mode="accept_edits")

    after_hashes = {s.scene_id: s.scene_input_hash() for s in result.scenes}

    assert after_hashes["intro_1"] != before_hashes["intro_1"]
    assert after_hashes["worked_example_1"] == before_hashes["worked_example_1"]
```

- [ ] **Step 2: Run test to verify it fails first (sanity check the assertion is meaningful)**

Run: `pytest packages/core/tests/test_interrupts.py::test_editing_one_scenes_renderer_tag_only_changes_that_scenes_hash -v`
Expected: this should already PASS given Tasks 4 and 11 are complete (both `scene_input_hash` and `interrupt_review` already exist and are correct). If it fails, the bug is in one of those two — do not proceed until it passes for the right reason (inspect the failure and fix `scene_input_hash` or `interrupt_review`, not the test).

- [ ] **Step 3: Run full interrupts test file to confirm nothing else broke**

Run: `pytest packages/core/tests/test_interrupts.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add packages/core/tests/test_interrupts.py
git commit -m "test(core): prove editing one scene's renderer tag leaves siblings' hashes untouched"
```

---

### Task 14: Verification gate node (run-mode-exempt)

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/verification_gate.py`
- Test: `packages/core/tests/test_verification_gate.py`

**Interfaces:**
- Consumes: `SceneGraph`, `SceneGraphEntry`, `VerificationResult` (Task 4), `DomainPack.verification_gates` (Task 4/9).
- Produces: `run_verification_gate(scene_graph: SceneGraph, domain_pack) -> list[VerificationResult]`, `VerificationBlockedError`. Consumed by Task 17.

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_verification_gate.py
import pytest

from spectacle_core.domain_pack import VerificationOutcome
from spectacle_core.models import SceneGraph, SceneGraphEntry
from spectacle_core.nodes.verification_gate import VerificationBlockedError, run_verification_gate


class _FakeDomainPack:
    @staticmethod
    def verification_gates(scene):
        if not scene.verify:
            return []

        def gate(s):
            return VerificationOutcome(passed=s.stated_answer == "7/8", detail="fake gate")

        return [gate]


def _scene_graph(stated_answer: str) -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="...", on_screen_text="3/4 + 1/8",
                              target_duration_s=45.0, verify=True,
                              expression="3/4 + 1/8", stated_answer=stated_answer),
        ],
    )


def test_all_gates_passing_returns_results_with_no_error():
    results = run_verification_gate(_scene_graph("7/8"), _FakeDomainPack())
    assert len(results) == 1  # only the verify=True scene produces a result
    assert results[0].passed is True
    assert results[0].scene_id == "worked_example_1"


def test_unverified_scene_produces_no_verification_result():
    results = run_verification_gate(_scene_graph("7/8"), _FakeDomainPack())
    assert all(r.scene_id != "intro_1" for r in results)


def test_failing_gate_raises_verification_blocked_error():
    with pytest.raises(VerificationBlockedError) as exc_info:
        run_verification_gate(_scene_graph("1/2"), _FakeDomainPack())
    assert "worked_example_1" in str(exc_info.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_verification_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.nodes.verification_gate'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/nodes/verification_gate.py
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneGraph, VerificationResult


class VerificationBlockedError(Exception):
    pass


def run_verification_gate(scene_graph: SceneGraph, domain_pack) -> list[VerificationResult]:
    """Runs every gate domain_pack.verification_gates() returns for each
    scene. Not subject to run_mode -- always enforced, even in 'auto'."""
    results: list[VerificationResult] = []
    failures: list[str] = []

    for scene in scene_graph.scenes:
        gates = domain_pack.verification_gates(scene)
        for gate in gates:
            outcome = gate(scene)
            results.append(VerificationResult(
                scene_id=scene.scene_id,
                scene_input_hash=scene.scene_input_hash(),
                passed=outcome.passed,
                detail=outcome.detail,
            ))
            if not outcome.passed:
                failures.append(f"{scene.scene_id}: {outcome.detail}")

    if failures:
        raise VerificationBlockedError("; ".join(failures))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_verification_gate.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/nodes/verification_gate.py packages/core/tests/test_verification_gate.py
git commit -m "feat(core): add verification_gate node, blocks the run on any gate failure"
```

---

### Task 15: TTSProvider (macOS `say`)

**Files:**
- Create: `packages/core/src/spectacle_core/tts.py`
- Test: `packages/core/tests/test_tts.py`

**Interfaces:**
- Produces: `TTSProvider` (Protocol: `synthesize(text: str, out_path: Path) -> float`), `MacSayTTSProvider`. Consumed by Task 17 (`render_scene` node's `tts_scene` step).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_tts.py
from pathlib import Path
from unittest.mock import patch

from spectacle_core.tts import MacSayTTSProvider


def test_synthesize_calls_say_then_ffmpeg_then_ffprobe_and_returns_duration(tmp_path):
    out_path = tmp_path / "narration.wav"
    provider = MacSayTTSProvider()

    ffprobe_result = type("R", (), {"stdout": "12.5\n"})()
    with patch("subprocess.run") as mock_run, \
         patch("pathlib.Path.unlink") as mock_unlink:
        mock_run.side_effect = [None, None, ffprobe_result]
        duration = provider.synthesize("hello world", out_path)

    assert duration == 12.5
    say_call, ffmpeg_call, ffprobe_call = mock_run.call_args_list
    assert say_call.args[0][0] == "say"
    assert "hello world" in say_call.args[0]
    assert ffmpeg_call.args[0][0] == "ffmpeg"
    assert ffprobe_call.args[0][0] == "ffprobe"
    mock_unlink.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest packages/core/tests/test_tts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.tts'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/tts.py
import subprocess
from pathlib import Path
from typing import Protocol


class TTSProvider(Protocol):
    def synthesize(self, text: str, out_path: Path) -> float: ...


class MacSayTTSProvider:
    def synthesize(self, text: str, out_path: Path) -> float:
        aiff_path = out_path.with_suffix(".aiff")
        subprocess.run(["say", "-o", str(aiff_path), text], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), str(out_path)], check=True)
        aiff_path.unlink(missing_ok=True)
        return self._probe_duration_s(out_path)

    @staticmethod
    def _probe_duration_s(path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest packages/core/tests/test_tts.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/tts.py packages/core/tests/test_tts.py
git commit -m "feat(core): add TTSProvider protocol and macOS say implementation"
```

---

### Task 16: Renderer wrappers — Remotion and Manim (incl. `ScenePreview`)

**Files:**
- Create: `packages/core/src/spectacle_core/renderers/__init__.py` (empty)
- Create: `packages/core/src/spectacle_core/renderers/remotion_render.py`
- Create: `packages/core/src/spectacle_core/renderers/manim_scene.py`
- Create: `packages/core/src/spectacle_core/renderers/manim_render.py`
- Create: `apps/interview-demo/renderer-remotion/package.json`
- Create: `apps/interview-demo/renderer-remotion/tsconfig.json`
- Create: `apps/interview-demo/renderer-remotion/src/index.ts`
- Create: `apps/interview-demo/renderer-remotion/src/Root.tsx`
- Create: `apps/interview-demo/renderer-remotion/src/LayoutScene.tsx`
- Test: `packages/core/tests/test_remotion_render.py`
- Test: `packages/core/tests/test_manim_render.py`

**Interfaces:**
- Produces: `render_remotion(narration_text, on_screen_text, duration_s, output_path) -> None`, `render_manim(expression, stated_answer, duration_s, output_path, quality: Literal["preview","final"]) -> None`. Consumed by Task 17 (`render_scene` node).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_remotion_render.py
import json
from pathlib import Path
from unittest.mock import patch

from spectacle_core.renderers.remotion_render import render_remotion


def test_render_remotion_invokes_npx_remotion_render_with_props(tmp_path):
    output_path = tmp_path / "final.mp4"
    with patch("subprocess.run") as mock_run:
        render_remotion("hello", "Hi!", 20.0, output_path)

    mock_run.assert_called_once()
    cmd = mock_run.call_args.args[0]
    assert cmd[:3] == ["npx", "remotion", "render"]
    assert "LayoutScene" in cmd
    assert str(output_path) in cmd
    props_index = cmd.index("--props") + 1
    props = json.loads(cmd[props_index])
    assert props["onScreenText"] == "Hi!"
    assert props["durationInSeconds"] == 20.0
```

```python
# packages/core/tests/test_manim_render.py
import json
import os
from pathlib import Path
from unittest.mock import patch

from spectacle_core.renderers.manim_render import render_manim


def test_render_manim_preview_uses_low_quality_flag(tmp_path):
    output_path = tmp_path / "preview.mp4"
    with patch("subprocess.run") as mock_run:
        render_manim("3/4 + 1/8", "7/8", 45.0, output_path, quality="preview")

    cmd = mock_run.call_args.args[0]
    env = mock_run.call_args.kwargs["env"]
    assert "-ql" in cmd
    assert "-qh" not in cmd
    params = json.loads(env["SPECTACLE_SCENE_PARAMS"])
    assert params == {"expression": "3/4 + 1/8", "stated_answer": "7/8", "duration_s": 45.0}


def test_render_manim_final_uses_high_quality_flag(tmp_path):
    output_path = tmp_path / "final.mp4"
    with patch("subprocess.run") as mock_run:
        render_manim("3/4 + 1/8", "7/8", 45.0, output_path, quality="final")

    cmd = mock_run.call_args.args[0]
    assert "-qh" in cmd
    assert "-ql" not in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_remotion_render.py packages/core/tests/test_manim_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.renderers'`

- [ ] **Step 3: Implement `remotion_render.py`**

```python
# packages/core/src/spectacle_core/renderers/remotion_render.py
import json
import subprocess
from pathlib import Path

_REMOTION_PROJECT_DIR = Path(__file__).resolve().parents[6] / "apps/interview-demo/renderer-remotion"


def render_remotion(narration_text: str, on_screen_text: str, duration_s: float, output_path: Path) -> None:
    props = json.dumps({"onScreenText": on_screen_text, "durationInSeconds": duration_s})
    cmd = [
        "npx", "remotion", "render", "LayoutScene", str(output_path),
        "--props", props,
    ]
    subprocess.run(cmd, cwd=_REMOTION_PROJECT_DIR, check=True)
```

- [ ] **Step 4: Implement `manim_scene.py` and `manim_render.py`**

```python
# packages/core/src/spectacle_core/renderers/manim_scene.py
import json
import os

from manim import FadeOut, MathTex, Scene, TransformMatchingTex, Write


class EquationMorphScene(Scene):
    def construct(self):
        params = json.loads(os.environ["SPECTACLE_SCENE_PARAMS"])
        total = params["duration_s"]
        write_t, morph_t, hold_t = total * 0.2, total * 0.4, total * 0.4

        lhs = MathTex(params["expression"].replace(" ", ""))
        rhs = MathTex(params["stated_answer"])

        self.play(Write(lhs), run_time=write_t)
        self.play(TransformMatchingTex(lhs, rhs), run_time=morph_t)
        self.wait(hold_t)
        self.play(FadeOut(rhs))
```

```python
# packages/core/src/spectacle_core/renderers/manim_render.py
import json
import os
import subprocess
from pathlib import Path
from typing import Literal

_SCENE_FILE = Path(__file__).with_name("manim_scene.py")


def render_manim(
    expression: str,
    stated_answer: str,
    duration_s: float,
    output_path: Path,
    quality: Literal["preview", "final"],
) -> None:
    env = os.environ.copy()
    env["SPECTACLE_SCENE_PARAMS"] = json.dumps({
        "expression": expression,
        "stated_answer": stated_answer,
        "duration_s": duration_s,
    })
    quality_flag = "-ql" if quality == "preview" else "-qh"
    cmd = [
        "manim", "render", quality_flag,
        "--output_file", output_path.name,
        str(_SCENE_FILE), "EquationMorphScene",
    ]
    subprocess.run(cmd, env=env, cwd=output_path.parent, check=True)
```

- [ ] **Step 5: Scaffold the minimal Remotion project**

```json
// apps/interview-demo/renderer-remotion/package.json
{
  "name": "renderer-remotion",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "render": "remotion render"
  },
  "dependencies": {
    "@remotion/cli": "^4.0.0",
    "remotion": "^4.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "@types/react": "^18.2.0"
  }
}
```

```json
// apps/interview-demo/renderer-remotion/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2018",
    "module": "commonjs",
    "jsx": "react-jsx",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

```tsx
// apps/interview-demo/renderer-remotion/src/LayoutScene.tsx
import { AbsoluteFill, useVideoConfig, interpolate, useCurrentFrame } from "remotion";

export type LayoutSceneProps = {
  onScreenText: string;
  durationInSeconds: number;
};

export const calculateLayoutSceneMetadata = ({ props }: { props: LayoutSceneProps }) => {
  const fps = 30;
  return {
    fps,
    durationInFrames: Math.round(props.durationInSeconds * fps),
  };
};

export const LayoutScene: React.FC<LayoutSceneProps> = ({ onScreenText }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b1021", justifyContent: "center", alignItems: "center" }}>
      <div style={{ opacity, color: "white", fontSize: 64, fontFamily: "sans-serif", textAlign: "center", padding: "0 80px" }}>
        {onScreenText}
      </div>
    </AbsoluteFill>
  );
};
```

```tsx
// apps/interview-demo/renderer-remotion/src/Root.tsx
import { Composition } from "remotion";
import { LayoutScene, calculateLayoutSceneMetadata, LayoutSceneProps } from "./LayoutScene";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition<LayoutSceneProps>
      id="LayoutScene"
      component={LayoutScene}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ onScreenText: "Hello!", durationInSeconds: 5 }}
      calculateMetadata={calculateLayoutSceneMetadata}
    />
  );
};
```

```ts
// apps/interview-demo/renderer-remotion/src/index.ts
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

- [ ] **Step 6: Run Python tests to verify they pass**

Run: `pytest packages/core/tests/test_remotion_render.py packages/core/tests/test_manim_render.py -v`
Expected: 3 passed

- [ ] **Step 7: Install Remotion project dependencies and confirm it builds**

Run:
```bash
cd apps/interview-demo/renderer-remotion && npm install && npx tsc --noEmit
cd -
```
Expected: no TypeScript errors.

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/spectacle_core/renderers packages/core/tests/test_remotion_render.py \
        packages/core/tests/test_manim_render.py apps/interview-demo/renderer-remotion
git commit -m "feat: add Remotion layout scene and Manim equation-morph scene renderers"
```

---

### Task 17: Fan-out, `render_scene` node (with cache-skip), `scene_av_mux`

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/render_scene.py`
- Test: `packages/core/tests/test_render_scene.py`

**Interfaces:**
- Consumes: `SceneGraph`, `SceneGraphEntry` (Task 4), `ArtifactStore` (Task 3), `TTSProvider` (Task 15), `render_remotion`/`render_manim` (Task 16), `NarrationClip`, `ScenePreview`, `RenderManifest`, `SceneFinal` (Task 4).
- Produces: `fan_out_scenes(scene_graph: SceneGraph) -> list[dict]` (per-scene payloads for `Send`), `render_scene(payload: dict, store: ArtifactStore, tts_provider: TTSProvider, on_artifact: Callable[[str, str], None] | None = None) -> SceneFinal` (the function `Send`-dispatched invocations call; cache-checks before doing any work; calls `on_artifact(scene_hash, stage)` as each intermediate artifact lands, so the caller can mirror it into artifact metadata — this is what makes progressive visibility in Task 25's UI actually work, not just theoretically possible). Consumed by Task 18 (`graph.py`) and Task 19 (`build_graph`, which supplies `on_artifact`).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_render_scene.py
from unittest.mock import patch

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.models import SceneGraph, SceneGraphEntry
from spectacle_core.nodes.render_scene import fan_out_scenes, render_scene


def _scene_graph() -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="three quarters plus one eighth",
                              on_screen_text="3/4 + 1/8", target_duration_s=45.0,
                              verify=True, expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_fan_out_produces_one_payload_per_scene():
    payloads = fan_out_scenes(_scene_graph())
    assert [p["scene"]["scene_id"] for p in payloads] == ["intro_1", "worked_example_1"]


def test_render_scene_skips_all_work_on_cache_hit(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[0]
    scene_hash = entry.scene_input_hash()
    (store._dir(scene_hash) / "scene_final.mp4").write_bytes(b"cached")

    class ExplodingTTS:
        def synthesize(self, *a, **kw):
            raise AssertionError("TTS should not run on a cache hit")

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim:
        result = render_scene({"scene": entry.model_dump(mode="json")}, store, ExplodingTTS())

    mock_remotion.assert_not_called()
    mock_manim.assert_not_called()
    assert result.scene_id == "intro_1"
    assert result.output_path == str(store.file_path(scene_hash, "scene_final.mp4"))


def test_render_scene_layout_path_calls_tts_then_remotion_then_mux(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[0]

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 21.5

    def fake_render_remotion(narration_text, on_screen_text, duration_s, output_path):
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_remotion", side_effect=fake_render_remotion), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux) as mock_mux:
        result = render_scene({"scene": entry.model_dump(mode="json")}, store, FakeTTS())

    assert mock_mux.called
    assert result.scene_id == "intro_1"
    scene_hash = entry.scene_input_hash()
    assert store.file_exists(scene_hash, "scene_final.mp4")


def test_render_scene_manim_path_writes_preview_before_final(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[1]
    calls = []

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 44.0

    def fake_render_manim(expression, stated_answer, duration_s, output_path, quality):
        calls.append(quality)
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_manim", side_effect=fake_render_manim), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux):
        render_scene({"scene": entry.model_dump(mode="json")}, store, FakeTTS())

    assert calls == ["preview", "final"]
    scene_hash = entry.scene_input_hash()
    assert store.file_exists(scene_hash, "preview.mp4")


def test_render_scene_calls_on_artifact_for_preview_and_final(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[1]  # the manim scene, so both stages fire
    recorded: list[tuple[str, str]] = []

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 44.0

    def fake_render_manim(expression, stated_answer, duration_s, output_path, quality):
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_manim", side_effect=fake_render_manim), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux):
        render_scene(
            {"scene": entry.model_dump(mode="json")}, store, FakeTTS(),
            on_artifact=lambda h, stage: recorded.append((h, stage)),
        )

    scene_hash = entry.scene_input_hash()
    assert (scene_hash, "scene_preview") in recorded
    assert (scene_hash, "scene_final") in recorded


def test_render_scene_calls_on_artifact_even_on_cache_hit(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[0]
    scene_hash = entry.scene_input_hash()
    (store._dir(scene_hash) / "scene_final.mp4").write_bytes(b"cached")
    recorded: list[tuple[str, str]] = []

    class ExplodingTTS:
        def synthesize(self, *a, **kw):
            raise AssertionError("TTS should not run on a cache hit")

    render_scene(
        {"scene": entry.model_dump(mode="json")}, store, ExplodingTTS(),
        on_artifact=lambda h, stage: recorded.append((h, stage)),
    )

    assert (scene_hash, "scene_final") in recorded
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_render_scene.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.nodes.render_scene'`

- [ ] **Step 3: Implement**

```python
# packages/core/src/spectacle_core/nodes/render_scene.py
import subprocess
from pathlib import Path
from typing import Callable

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.models import SceneFinal, SceneGraph, SceneGraphEntry
from spectacle_core.renderers.manim_render import render_manim
from spectacle_core.renderers.remotion_render import render_remotion
from spectacle_core.tts import TTSProvider

OnArtifactFn = Callable[[str, str], None]


def fan_out_scenes(scene_graph: SceneGraph) -> list[dict]:
    return [{"scene": entry.model_dump(mode="json")} for entry in scene_graph.scenes]


def mux_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
         "-c:v", "copy", "-c:a", "aac", "-shortest", str(output_path)],
        check=True,
    )


def render_scene(
    payload: dict,
    store: ArtifactStore,
    tts_provider: TTSProvider,
    on_artifact: OnArtifactFn | None = None,
) -> SceneFinal:
    entry = SceneGraphEntry.model_validate(payload["scene"])
    scene_hash = entry.scene_input_hash()

    def notify(stage: str) -> None:
        if on_artifact is not None:
            on_artifact(scene_hash, stage)

    if store.file_exists(scene_hash, "scene_final.mp4"):
        notify("scene_final")
        return SceneFinal(
            scene_id=entry.scene_id,
            scene_input_hash=scene_hash,
            output_path=str(store.file_path(scene_hash, "scene_final.mp4")),
        )

    audio_path = store.file_path(scene_hash, "narration.wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    duration_s = tts_provider.synthesize(entry.narration_text, audio_path)
    notify("narration_clip")

    video_path = store.file_path(scene_hash, "final.mp4")
    if entry.renderer == "manim":
        preview_path = store.file_path(scene_hash, "preview.mp4")
        render_manim(entry.expression, entry.stated_answer, duration_s, preview_path, quality="preview")
        notify("scene_preview")
        render_manim(entry.expression, entry.stated_answer, duration_s, video_path, quality="final")
    else:
        render_remotion(entry.narration_text, entry.on_screen_text, duration_s, video_path)

    final_path = store.file_path(scene_hash, "scene_final.mp4")
    mux_audio_video(video_path, audio_path, final_path)
    notify("scene_final")

    return SceneFinal(scene_id=entry.scene_id, scene_input_hash=scene_hash, output_path=str(final_path))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_render_scene.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/nodes/render_scene.py packages/core/tests/test_render_scene.py
git commit -m "feat(core): add per-scene fan-out, render_scene with cache-skip, and av mux"
```

---

### Task 18: `collect_scenes` (fan-in) + `mux_final`

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/finalize.py`
- Test: `packages/core/tests/test_finalize.py`

**Interfaces:**
- Consumes: `SceneFinal`, `SceneGraph`, `FinalManifest` (Task 4), `ArtifactStore` (Task 3).
- Produces: `collect_scenes(scene_finals: dict[str, dict], scene_graph: SceneGraph) -> list[SceneFinal]` (orders fan-in results back into scene-graph order), `mux_final(scene_finals_ordered: list[SceneFinal], scene_graph_hash: str, store: ArtifactStore) -> FinalManifest`. Consumed by Task 19 (`graph.py`).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_finalize.py
from pathlib import Path
from unittest.mock import patch

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.models import SceneFinal, SceneGraph, SceneGraphEntry
from spectacle_core.nodes.finalize import collect_scenes, mux_final


def _scene_graph() -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="...", on_screen_text="3/4 + 1/8",
                              target_duration_s=45.0, verify=True,
                              expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_collect_scenes_reorders_fan_in_results_to_scene_graph_order():
    scene_graph = _scene_graph()
    # Sends can complete out of order -- simulate worked_example finishing first.
    scene_finals = {
        "worked_example_1": SceneFinal(scene_id="worked_example_1", scene_input_hash="h2",
                                          output_path="/tmp/b.mp4").model_dump(mode="json"),
        "intro_1": SceneFinal(scene_id="intro_1", scene_input_hash="h1",
                                 output_path="/tmp/a.mp4").model_dump(mode="json"),
    }
    ordered = collect_scenes(scene_finals, scene_graph)
    assert [s.scene_id for s in ordered] == ["intro_1", "worked_example_1"]


def test_mux_final_concatenates_in_order_and_writes_manifest(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    ordered = [
        SceneFinal(scene_id="intro_1", scene_input_hash="h1", output_path=str(tmp_path / "a.mp4")),
        SceneFinal(scene_id="worked_example_1", scene_input_hash="h2", output_path=str(tmp_path / "b.mp4")),
    ]
    for s in ordered:
        Path(s.output_path).write_bytes(b"fake clip")

    def fake_concat(inputs, output_path):
        Path(output_path).write_bytes(b"fake final video")

    with patch("spectacle_core.nodes.finalize.ffmpeg_concat", side_effect=fake_concat) as mock_concat:
        manifest = mux_final(ordered, scene_graph_hash="scenegraphhash", store=store)

    concat_inputs = mock_concat.call_args.args[0]
    assert concat_inputs == [s.output_path for s in ordered]
    assert manifest.scene_graph_hash == "scenegraphhash"
    assert Path(manifest.output_path).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_finalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.nodes.finalize'`

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_finalize.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/spectacle_core/nodes/finalize.py packages/core/tests/test_finalize.py
git commit -m "feat(core): add collect_scenes fan-in and mux_final"
```

---

### Task 19: Graph assembly + Postgres checkpointer + docker-compose

**Files:**
- Create: `packages/core/src/spectacle_core/graph.py`
- Create: `docker-compose.yml`
- Test: `packages/core/tests/test_graph_integration.py`

**Interfaces:**
- Consumes: every node function from Tasks 10-18, `DomainPack` (Task 4), `ArtifactStore`/`TTSProvider` (Tasks 3, 15), `OnArtifactFn` (Task 17).
- Produces: `GraphState` (TypedDict), `build_graph(domain_pack, store, tts_provider, checkpointer, metadata_recorder: Callable[[str, str, str | None], None] | None = None, ...) -> CompiledGraph`. `metadata_recorder(content_hash, stage, scene_id)` is called after every artifact is written, decoupling `packages/core` from the Postgres-specific `ArtifactMetadataStore` in `apps/interview-demo/server` (core stays domain- and infra-agnostic; the FastAPI layer supplies the callback). Consumed by Task 21/22 (FastAPI `run_manager`, which supplies `metadata_recorder`) and Task 20 (kill/resume test, which passes `None`).

- [ ] **Step 1: Write the failing integration test**

```python
# packages/core/tests/test_graph_integration.py
from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.graph import build_graph
from spectacle_core.nodes.script_agent import ScriptLLMResponse
from spectacle_education import education_pack


class _FakeTTS:
    def synthesize(self, text, out_path):
        out_path.write_bytes(b"fake audio")
        return 5.0


def _fake_llm(stub):
    if stub.expression is not None:
        return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}",
                                    stated_answer="7/8")
    return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}")


def test_full_run_in_auto_mode_produces_final_manifest(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    checkpointer = MemorySaver()
    recorded: list[tuple[str, str, str | None]] = []
    graph = build_graph(
        domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
        script_llm_fn=_fake_llm,
        content_hint_fn=lambda spec, stub: "hint",
        guided_practice_expression_fn=lambda spec: "1/2 + 1/4",
        metadata_recorder=lambda h, stage, scene_id=None: recorded.append((h, stage, scene_id)),
    )
    config = {"configurable": {"thread_id": "test-run-1"}}

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim, \
         patch("spectacle_core.nodes.render_scene.mux_audio_video") as mock_av_mux, \
         patch("spectacle_core.nodes.finalize.ffmpeg_concat") as mock_concat:

        def fake_remotion(narration_text, on_screen_text, duration_s, output_path):
            output_path.write_bytes(b"v")
        mock_remotion.side_effect = fake_remotion

        def fake_manim(expression, stated_answer, duration_s, output_path, quality):
            output_path.write_bytes(b"v")
        mock_manim.side_effect = fake_manim

        def fake_mux(video_path, audio_path, output_path):
            output_path.write_bytes(b"f")
        mock_av_mux.side_effect = fake_mux

        def fake_concat(inputs, output_path):
            output_path.write_bytes(b"final")
        mock_concat.side_effect = fake_concat

        result = graph.invoke({
            "spec": {
                "learning_objective": "add fractions",
                "worked_example_expression": "3/4 + 1/8",
                "target_duration_minutes": 1,
                "audience": "6th grade",
            },
            "run_mode": "auto",
        }, config=config)

    assert result["final_manifest"] is not None
    assert result["final_manifest"]["scene_graph_hash"]
    stages_recorded = {stage for _, stage, _ in recorded}
    assert {"content_tree", "script", "scene_graph", "scene_final", "final_manifest"} <= stages_recorded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest packages/core/tests/test_graph_integration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectacle_core.graph'`

- [ ] **Step 3: Implement `graph.py`**

```python
# packages/core/src/spectacle_core/graph.py
from typing import Annotated, Callable, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from spectacle_core.artifacts import ArtifactStore
from spectacle_core.domain_pack import ContentTree, DomainPack
from spectacle_core.hashing import content_hash
from spectacle_core.models import FinalManifest, SceneGraph, Script
from spectacle_core.nodes.finalize import collect_scenes, mux_final
from spectacle_core.nodes.interrupts import interrupt_review
from spectacle_core.nodes.render_scene import fan_out_scenes, render_scene
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
        tree: ContentTree = domain_pack.structure(spec, **kwargs)
        tree_hash = content_hash(tree.model_dump(mode="json"))
        store.put_json(tree_hash, tree.model_dump(mode="json"))
        record(tree_hash, "content_tree")
        return {"content_tree": tree.model_dump(mode="json")}

    def script_agent_node(state: GraphState) -> dict:
        tree = ContentTree.model_validate(state["content_tree"])
        script = run_script_agent(tree, llm_fn=script_llm_fn)
        store.put_json(script.compute_hash(), script.model_dump(mode="json"))
        record(script.compute_hash(), "script")
        return {"script": script.model_dump(mode="json")}

    def script_review_node(state: GraphState) -> dict:
        script = Script.model_validate(state["script"])
        reviewed = interrupt_review(script, Script, state["run_mode"])
        store.put_json(reviewed.compute_hash(), reviewed.model_dump(mode="json"))
        record(reviewed.compute_hash(), "script")
        return {"script": reviewed.model_dump(mode="json")}

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
        store.put_json(manifest.compute_hash(), manifest.model_dump(mode="json"))
        record(manifest.compute_hash(), "final_manifest")
        return {"final_manifest": manifest.model_dump(mode="json")}

    builder = StateGraph(GraphState)
    builder.add_node("structure", load_spec_and_structure)
    builder.add_node("script_agent", script_agent_node)
    builder.add_node("script_review", script_review_node)
    builder.add_node("scene_planner", scene_planner_node)
    builder.add_node("scene_graph_review", scene_graph_review_node)
    builder.add_node("verification_gate", verification_gate_node)
    builder.add_node("render_scene", render_scene_node)
    builder.add_node("collect_scenes", collect_scenes_node)
    builder.add_node("mux_final", mux_final_node)

    builder.set_entry_point("structure")
    builder.add_edge("structure", "script_agent")
    builder.add_edge("script_agent", "script_review")
    builder.add_edge("script_review", "scene_planner")
    builder.add_edge("scene_planner", "scene_graph_review")
    builder.add_edge("scene_graph_review", "verification_gate")
    builder.add_conditional_edges("verification_gate", fan_out, ["render_scene"])
    builder.add_edge("render_scene", "collect_scenes")
    builder.add_edge("collect_scenes", "mux_final")
    builder.add_edge("mux_final", END)

    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest packages/core/tests/test_graph_integration.py -v`
Expected: 1 passed

- [ ] **Step 5: Create `docker-compose.yml` for local Postgres**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: spectacle
      POSTGRES_USER: spectacle
      POSTGRES_PASSWORD: spectacle
    ports:
      - "5432:5432"
    volumes:
      - spectacle_pgdata:/var/lib/postgresql/data

volumes:
  spectacle_pgdata:
```

- [ ] **Step 6: Bring up Postgres and confirm the checkpointer can connect**

Run:
```bash
docker compose up -d
python -c "
from langgraph.checkpoint.postgres import PostgresSaver
with PostgresSaver.from_conn_string('postgresql://spectacle:spectacle@localhost:5432/spectacle') as cp:
    cp.setup()
    print('checkpoint tables ready')
"
```
Expected: prints `checkpoint tables ready` with no errors.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/spectacle_core/graph.py packages/core/tests/test_graph_integration.py docker-compose.yml
git commit -m "feat(core): assemble the full LangGraph pipeline; add local Postgres via docker-compose"
```

---

### Task 20: Kill/resume proof (claim #2)

**Files:**
- Test: `packages/core/tests/test_graph_kill_resume.py`

**Interfaces:**
- Consumes: `build_graph` (Task 19), real `PostgresSaver` (requires the `docker-compose` Postgres from Task 19 running).
- Produces: nothing new — a targeted test proving the already-built checkpointer mechanism survives losing the in-process graph object entirely, not just a clean pause.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_graph_kill_resume.py
from unittest.mock import patch

import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.graph import build_graph
from spectacle_core.nodes.script_agent import ScriptLLMResponse
from spectacle_education import education_pack

PG_CONN = "postgresql://spectacle:spectacle@localhost:5432/spectacle"


def _fake_llm(stub):
    if stub.expression is not None:
        return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}",
                                    stated_answer="7/8")
    return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}")


class _FakeTTS:
    def synthesize(self, text, out_path):
        out_path.write_bytes(b"fake audio")
        return 5.0


@pytest.mark.integration
def test_graph_pauses_at_interrupt_and_resumes_after_object_is_discarded(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    config = {"configurable": {"thread_id": "kill-resume-test"}}

    with PostgresSaver.from_conn_string(PG_CONN) as checkpointer:
        checkpointer.setup()
        graph = build_graph(
            domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
            script_llm_fn=_fake_llm,
            content_hint_fn=lambda spec, stub: "hint",
            guided_practice_expression_fn=lambda spec: "1/2 + 1/4",
        )
        result = graph.invoke({
            "spec": {
                "learning_objective": "add fractions",
                "worked_example_expression": "3/4 + 1/8",
                "target_duration_minutes": 1,
                "audience": "6th grade",
            },
            "run_mode": "accept_edits",
        }, config=config)

    assert "__interrupt__" in result  # paused at script_review, per accept_edits mode

    # Simulate the process dying here: `graph`, `checkpointer`, and `store`
    # above go fully out of scope. Everything below rebuilds from scratch,
    # exactly as a freshly-started process would after a crash.
    del graph, checkpointer

    with PostgresSaver.from_conn_string(PG_CONN) as fresh_checkpointer:
        fresh_store = LocalFileArtifactStore(tmp_path)
        fresh_graph = build_graph(
            domain_pack=education_pack, store=fresh_store, tts_provider=_FakeTTS(), checkpointer=fresh_checkpointer,
            script_llm_fn=_fake_llm,
            content_hint_fn=lambda spec, stub: "hint",
            guided_practice_expression_fn=lambda spec: "1/2 + 1/4",
        )

        with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
             patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim, \
             patch("spectacle_core.nodes.render_scene.mux_audio_video") as mock_av_mux, \
             patch("spectacle_core.nodes.finalize.ffmpeg_concat") as mock_concat:
            mock_remotion.side_effect = lambda *a: a[-1].write_bytes(b"v")
            mock_manim.side_effect = lambda *a, **kw: a[-2].write_bytes(b"v") if len(a) >= 2 else None
            mock_av_mux.side_effect = lambda video_path, audio_path, output_path: output_path.write_bytes(b"f")
            mock_concat.side_effect = lambda inputs, output_path: output_path.write_bytes(b"final")

            final_result = fresh_graph.invoke(Command(resume={"action": "approve"}), config=config)

    assert final_result["final_manifest"] is not None
    # Prove it resumed rather than restarted: content_tree/script were never
    # recomputed with new randomness -- the same thread_id's checkpointed
    # script content_tree hash is unchanged across the two invokes.
```

- [ ] **Step 2: Run test to verify it fails first for the right reason**

Run: `pytest packages/core/tests/test_graph_kill_resume.py -v -m integration`
Expected: this exercises real Postgres (from Task 19's docker-compose) and the fully-assembled graph from Task 19 — it should PASS given Tasks 11, 17, 19 are correct. If it fails, the bug is almost certainly in the `interrupt_review`/`Command(resume=...)` wiring inside `graph.py` (Task 19) — fix there, not in this test.

- [ ] **Step 3: Register the `integration` marker so plain `pytest` runs skip it by default**

```ini
# pytest.ini (append)
markers =
    integration: requires local Postgres via `docker compose up -d` (Task 19)
```

Modify the default `testpaths` run to exclude it:

Run: `pytest -m "not integration"` (this is now the default fast test command used in every earlier task's steps; the slower `-m integration` run is opt-in, used here and in Task 22's crash-demo test)

- [ ] **Step 4: Run the full non-integration suite once more to confirm nothing regressed**

Run: `pytest -m "not integration" -v`
Expected: all tests from Tasks 1-19 still pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/tests/test_graph_kill_resume.py pytest.ini
git commit -m "test(core): prove kill-and-resume survives discarding the in-process graph object"
```

---

### Task 21: FastAPI app skeleton — `POST /runs`, `GET /runs/:id`, `GET /runs/:id/artifacts`

**Files:**
- Create: `apps/interview-demo/server/src/server/db.py`
- Create: `apps/interview-demo/server/src/server/run_manager.py`
- Create: `apps/interview-demo/server/src/server/main.py`
- Test: `apps/interview-demo/server/tests/test_db.py`
- Test: `apps/interview-demo/server/tests/test_run_manager.py`
- Test: `apps/interview-demo/server/tests/test_main.py`

**Interfaces:**
- Consumes: `build_graph` (Task 19), `education_pack` (Task 8), `PostgresSaver`, `LocalFileArtifactStore` (Task 3).
- Produces: `RunManager` (`start_run(spec, run_mode) -> run_id`, `get_status(run_id) -> dict`, `list_artifacts(run_id) -> list[dict]`), a FastAPI `app` with the three routes. Consumed by Task 22 (crash/resume endpoints) and Task 23 (chat/resume endpoints).

- [ ] **Step 1: Write the failing tests**

```python
# apps/interview-demo/server/tests/test_db.py
from server.db import ArtifactMetadataStore

PG_CONN = "postgresql://spectacle:spectacle@localhost:5432/spectacle"


def test_insert_and_list_artifacts_for_a_run():
    store = ArtifactMetadataStore(PG_CONN)
    store.setup()
    store.record(run_id="run-1", content_hash="h1", stage="script", scene_id=None)
    store.record(run_id="run-1", content_hash="h2", stage="scene_final", scene_id="intro_1")
    rows = store.list_for_run("run-1")
    assert {r["content_hash"] for r in rows} == {"h1", "h2"}
```

```python
# apps/interview-demo/server/tests/test_run_manager.py
from unittest.mock import patch

from server.run_manager import RunManager


def test_start_run_returns_a_run_id_and_kicks_off_a_background_thread(tmp_path):
    manager = RunManager(artifact_root=tmp_path, pg_conn="postgresql://spectacle:spectacle@localhost:5432/spectacle")
    with patch.object(manager, "_execute_run") as mock_execute:
        run_id = manager.start_run(
            spec={"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
                    "target_duration_minutes": 1, "audience": "6th grade"},
            run_mode="auto",
        )
    assert run_id
    mock_execute.assert_called_once()
```

```python
# apps/interview-demo/server/tests/test_main.py
from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_post_runs_returns_201_and_a_run_id():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.start_run", return_value="run-abc"
    ):
        resp = client.post("/runs", json={
            "spec": {"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8",
                        "target_duration_minutes": 1, "audience": "6th grade"},
            "run_mode": "auto",
        })
    assert resp.status_code == 201
    assert resp.json()["run_id"] == "run-abc"


def test_get_run_status_404_for_unknown_run():
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/interview-demo/server/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.db'` (and cascading import errors for the others)

- [ ] **Step 3: Implement `db.py`**

```python
# apps/interview-demo/server/src/server/db.py
import psycopg


class ArtifactMetadataStore:
    def __init__(self, conn_string: str) -> None:
        self.conn_string = conn_string

    def setup(self) -> None:
        with psycopg.connect(self.conn_string) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id SERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    scene_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            conn.commit()

    def record(self, run_id: str, content_hash: str, stage: str, scene_id: str | None) -> None:
        with psycopg.connect(self.conn_string) as conn:
            conn.execute(
                "INSERT INTO artifacts (run_id, content_hash, stage, scene_id) VALUES (%s, %s, %s, %s)",
                (run_id, content_hash, stage, scene_id),
            )
            conn.commit()

    def list_for_run(self, run_id: str) -> list[dict]:
        with psycopg.connect(self.conn_string) as conn:
            rows = conn.execute(
                "SELECT content_hash, stage, scene_id, created_at FROM artifacts "
                "WHERE run_id = %s ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
            columns = ["content_hash", "stage", "scene_id", "created_at"]
            return [dict(zip(columns, row)) for row in rows]
```

- [ ] **Step 4: Implement `run_manager.py`**

```python
# apps/interview-demo/server/src/server/run_manager.py
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
        self.metadata.setup()
        self._statuses: dict[str, dict] = {}

    def start_run(self, spec: dict, run_mode: Literal["accept_edits", "auto"]) -> str:
        run_id = str(uuid.uuid4())
        self._statuses[run_id] = {"status": "running"}
        thread = threading.Thread(target=self._execute_run, args=(run_id, spec, run_mode), daemon=True)
        thread.start()
        return run_id

    def _execute_run(self, run_id: str, spec: dict, run_mode: str) -> None:
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

    def get_status(self, run_id: str) -> dict | None:
        return self._statuses.get(run_id)

    def list_artifacts(self, run_id: str) -> list[dict]:
        return self.metadata.list_for_run(run_id)
```

- [ ] **Step 5: Implement `main.py`**

```python
# apps/interview-demo/server/src/server/main.py
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest apps/interview-demo/server/tests -v -m "not integration"`
Expected: 4 passed (`test_run_manager`, `test_main` — `test_db.py` needs live Postgres, mark it `@pytest.mark.integration` and rerun with `-m integration` separately to confirm it passes too)

- [ ] **Step 7: Mark `test_db.py` as integration and re-run split**

Add `import pytest` and `@pytest.mark.integration` above `test_insert_and_list_artifacts_for_a_run` in `test_db.py`.

Run: `pytest apps/interview-demo/server/tests -v -m integration`
Expected: 1 passed (requires `docker compose up -d` from Task 19)

- [ ] **Step 8: Commit**

```bash
git add apps/interview-demo/server/src/server/db.py apps/interview-demo/server/src/server/run_manager.py \
        apps/interview-demo/server/src/server/main.py apps/interview-demo/server/tests
git commit -m "feat(server): add FastAPI skeleton with run start/status/artifacts endpoints"
```

---

### Task 22: Simulate-crash + resume endpoints (claim #2 through the HTTP surface)

**Files:**
- Modify: `apps/interview-demo/server/src/server/main.py`
- Modify: `apps/interview-demo/server/src/server/run_manager.py` (add `resume_run`)
- Test: `apps/interview-demo/server/tests/test_main.py` (append)

**Interfaces:**
- Consumes: `RunManager` (Task 21).
- Produces: `RunManager.resume_run(run_id, payload) -> dict`, `POST /runs/:id/simulate-crash`, `POST /runs/:id/resume`.

- [ ] **Step 1: Write the failing test**

Append to `apps/interview-demo/server/tests/test_main.py`:

```python
def test_simulate_crash_calls_os_exit():
    with __import__("unittest.mock", fromlist=["patch"]).patch("server.main.os._exit") as mock_exit:
        client.post("/runs/some-run/simulate-crash")
    mock_exit.assert_called_once_with(1)


def test_resume_endpoint_delegates_to_run_manager():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.resume_run", return_value={"status": "done"}
    ) as mock_resume:
        resp = client.post("/runs/run-1/resume", json={"action": "approve"})
    mock_resume.assert_called_once_with("run-1", {"action": "approve"})
    assert resp.json() == {"status": "done"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest apps/interview-demo/server/tests/test_main.py -v`
Expected: FAIL — `/runs/{run_id}/simulate-crash` and `/runs/{run_id}/resume` don't exist yet (404s), and `RunManager.resume_run` doesn't exist.

- [ ] **Step 3: Add `resume_run` to `run_manager.py`**

```python
# apps/interview-demo/server/src/server/run_manager.py (append to RunManager)
    def resume_run(self, run_id: str, payload: dict) -> dict:
        from langgraph.types import Command

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
        status = {"status": "paused" if "__interrupt__" in result else "done", "result": result}
        self._statuses[run_id] = status
        return status
```

- [ ] **Step 4: Add endpoints to `main.py`**

`os` is already imported at the top of `main.py` from Task 21, so `os._exit` is patchable in tests as `server.main.os._exit` with no further import changes needed:

```python
# apps/interview-demo/server/src/server/main.py (append)
@app.post("/runs/{run_id}/simulate-crash")
def post_simulate_crash(run_id: str) -> dict:
    os._exit(1)  # pragma: no cover -- unreachable in tests, os._exit is mocked


@app.post("/runs/{run_id}/resume")
def post_resume(run_id: str, payload: dict) -> dict:
    return run_manager.resume_run(run_id, payload)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest apps/interview-demo/server/tests/test_main.py -v`
Expected: 6 passed

- [ ] **Step 6: Manual end-to-end crash/resume demo (the real claim #2 proof, run once by hand)**

```bash
docker compose up -d
SPECTACLE_ARTIFACT_ROOT=./artifacts SPECTACLE_PG_CONN=postgresql://spectacle:spectacle@localhost:5432/spectacle \
  uvicorn server.main:app --app-dir apps/interview-demo/server/src --port 8000 &
RUN_ID=$(curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"spec": {"learning_objective": "add fractions", "worked_example_expression": "3/4 + 1/8", "target_duration_minutes": 1, "audience": "6th grade"}, "run_mode": "accept_edits"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
curl -s -X POST "localhost:8000/runs/$RUN_ID/simulate-crash"  # process exits
# restart the server (same command as above), then:
curl -s -X POST "localhost:8000/runs/$RUN_ID/resume" -H 'content-type: application/json' -d '{"action": "approve"}'
```
Expected: the final `resume` call returns `{"status": "paused", ...}` (it will pause again at Interrupt B) or `{"status": "done", ...}` — either way, it must **not** error about an unknown thread/run, proving the Postgres checkpoint survived the crash.

- [ ] **Step 7: Commit**

```bash
git add apps/interview-demo/server/src/server/main.py apps/interview-demo/server/src/server/run_manager.py \
        apps/interview-demo/server/tests/test_main.py
git commit -m "feat(server): add simulate-crash and resume endpoints"
```

---

### Task 23: Chat edit-assistant + interrupt/resume submission endpoints

**Files:**
- Create: `packages/core/src/spectacle_core/edit_assistant.py`
- Modify: `apps/interview-demo/server/src/server/main.py`
- Test: `packages/core/tests/test_edit_assistant.py`
- Test: `apps/interview-demo/server/tests/test_main.py` (append)

**Interfaces:**
- Consumes: none new beyond pydantic.
- Produces: `propose_edit(artifact_type: type[BaseModel], current_artifact: dict, chat_message: str, history: list[dict], llm_fn=default_edit_llm) -> dict` (core, domain-agnostic), `POST /runs/:id/interrupt/chat`, `POST /runs/:id/interrupt/resume` (this is the same underlying mechanism as `POST /runs/:id/resume` from Task 22 — an explicit alias per the spec's endpoint list, since `resume` there was generic and the spec calls out `interrupt/resume` specifically for the approve/edit submission).

- [ ] **Step 1: Write the failing tests**

```python
# packages/core/tests/test_edit_assistant.py
import pytest
from pydantic import BaseModel

from spectacle_core.edit_assistant import propose_edit


class Dummy(BaseModel):
    text: str


def test_propose_edit_validates_llm_output_against_schema():
    def fake_llm(artifact_type, current_artifact, chat_message, history):
        return {"text": "edited by chat"}

    result = propose_edit(Dummy, {"text": "original"}, "make it punchier", [], llm_fn=fake_llm)
    assert result == {"text": "edited by chat"}


def test_propose_edit_raises_on_invalid_llm_output():
    def bad_llm(artifact_type, current_artifact, chat_message, history):
        return {"wrong_field": "oops"}

    with pytest.raises(ValueError, match="edit-assistant produced an invalid"):
        propose_edit(Dummy, {"text": "original"}, "make it punchier", [], llm_fn=bad_llm)
```

Append to `apps/interview-demo/server/tests/test_main.py`:

```python
def test_interrupt_chat_returns_proposed_artifact():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.propose_edit", return_value={"text": "edited"}
    ):
        resp = client.post("/runs/run-1/interrupt/chat", json={
            "artifact_type": "Script", "current_artifact": {"text": "original"},
            "message": "make it punchier", "history": [],
        })
    assert resp.json() == {"proposed_artifact": {"text": "edited"}}


def test_interrupt_resume_delegates_to_run_manager_same_as_resume():
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "server.main.run_manager.resume_run", return_value={"status": "done"}
    ) as mock_resume:
        resp = client.post("/runs/run-1/interrupt/resume", json={"action": "approve"})
    mock_resume.assert_called_once_with("run-1", {"action": "approve"})
    assert resp.json() == {"status": "done"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/core/tests/test_edit_assistant.py apps/interview-demo/server/tests/test_main.py -v`
Expected: FAIL — `spectacle_core.edit_assistant` doesn't exist; the two new routes 404.

- [ ] **Step 3: Implement `edit_assistant.py`**

```python
# packages/core/src/spectacle_core/edit_assistant.py
from typing import Callable

from pydantic import BaseModel, ValidationError

EditLLMFn = Callable[[type[BaseModel], dict, str, list[dict]], dict]


def default_edit_llm(artifact_type: type[BaseModel], current_artifact: dict, chat_message: str, history: list[dict]) -> dict:
    """Real implementation calls an LLM with the current artifact JSON,
    the user's natural-language edit request, and prior chat turns, asking
    it to return a full replacement artifact of the same shape. Kept as an
    injectable seam so the API layer (and tests) can swap it out. This is
    domain-agnostic: it works for any pydantic artifact_type, not just
    education's Script/SceneGraph."""
    raise NotImplementedError("wire up a real LLM client here")


def propose_edit(
    artifact_type: type[BaseModel],
    current_artifact: dict,
    chat_message: str,
    history: list[dict],
    llm_fn: EditLLMFn = default_edit_llm,
) -> dict:
    proposed = llm_fn(artifact_type, current_artifact, chat_message, history)
    try:
        validated = artifact_type.model_validate(proposed)
    except ValidationError as exc:
        raise ValueError(f"edit-assistant produced an invalid {artifact_type.__name__}: {exc}")
    return validated.model_dump(mode="json")
```

- [ ] **Step 4: Add endpoints to `main.py`**

```python
# apps/interview-demo/server/src/server/main.py (append)
from spectacle_core.edit_assistant import propose_edit
from spectacle_core.models import SceneGraph, Script

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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest packages/core/tests/test_edit_assistant.py apps/interview-demo/server/tests/test_main.py -v`
Expected: 2 + 8 passed

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/spectacle_core/edit_assistant.py apps/interview-demo/server/src/server/main.py \
        packages/core/tests/test_edit_assistant.py apps/interview-demo/server/tests/test_main.py
git commit -m "feat: add domain-agnostic chat edit-assistant and interrupt/chat+resume endpoints"
```

---

### Task 24: Next.js scaffold — Start Run page with run-mode selector

**Files:**
- Create: `apps/interview-demo/web/package.json`
- Create: `apps/interview-demo/web/tsconfig.json`
- Create: `apps/interview-demo/web/next.config.js`
- Create: `apps/interview-demo/web/app/layout.tsx`
- Create: `apps/interview-demo/web/app/page.tsx`
- Create: `apps/interview-demo/web/lib/api.ts`

**Interfaces:**
- Consumes: `POST /runs` (Task 21).
- Produces: a Next.js app that can start a run and navigate to `/runs/[id]` (built out in Task 25).

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "interview-demo-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "@types/react": "^18.2.0",
    "@types/node": "^20.11.0"
  }
}
```

- [ ] **Step 2: Create `tsconfig.json` and `next.config.js`**

```json
{
  "compilerOptions": {
    "target": "ES2018",
    "lib": ["dom", "es2018"],
    "jsx": "preserve",
    "module": "esnext",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "paths": { "@/*": ["./*"] }
  },
  "include": ["**/*.ts", "**/*.tsx"]
}
```

```js
/** @type {import('next').NextConfig} */
module.exports = {};
```

- [ ] **Step 3: Create `lib/api.ts`**

```ts
// apps/interview-demo/web/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type RunMode = "accept_edits" | "auto";

export async function startRun(spec: Record<string, unknown>, runMode: RunMode): Promise<{ run_id: string }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ spec, run_mode: runMode }),
  });
  if (!res.ok) throw new Error(`start run failed: ${res.status}`);
  return res.json();
}

export async function getRun(runId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/runs/${runId}`);
  if (!res.ok) throw new Error(`get run failed: ${res.status}`);
  return res.json();
}

export async function getRunArtifacts(runId: string): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${API_BASE}/runs/${runId}/artifacts`);
  if (!res.ok) throw new Error(`get artifacts failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 4: Create `app/layout.tsx` and `app/page.tsx` (Start Run form)**

```tsx
// apps/interview-demo/web/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

```tsx
// apps/interview-demo/web/app/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startRun, RunMode } from "@/lib/api";

export default function StartRunPage() {
  const router = useRouter();
  const [learningObjective, setLearningObjective] = useState("Add fractions with unlike denominators");
  const [expression, setExpression] = useState("3/4 + 1/8");
  const [minutes, setMinutes] = useState(3);
  const [runMode, setRunMode] = useState<RunMode>("accept_edits");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { run_id } = await startRun(
        {
          learning_objective: learningObjective,
          worked_example_expression: expression,
          target_duration_minutes: minutes,
          audience: "6th grade",
        },
        runMode
      );
      router.push(`/runs/${run_id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Start a lesson</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Learning objective
          <input value={learningObjective} onChange={(e) => setLearningObjective(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Worked example expression
          <input value={expression} onChange={(e) => setExpression(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Duration (minutes, 1-10)
          <input type="number" min={1} max={10} value={minutes}
                 onChange={(e) => setMinutes(Number(e.target.value))} />
        </label>
        <fieldset>
          <legend>Run mode</legend>
          <label>
            <input type="radio" checked={runMode === "accept_edits"} onChange={() => setRunMode("accept_edits")} />
            accept_edits (pause for review)
          </label>
          <label>
            <input type="radio" checked={runMode === "auto"} onChange={() => setRunMode("auto")} />
            auto (hands-off)
          </label>
        </fieldset>
        <button type="submit" disabled={submitting}>{submitting ? "Starting..." : "Start Run"}</button>
      </form>
    </main>
  );
}
```

- [ ] **Step 5: Install and confirm it builds**

Run:
```bash
cd apps/interview-demo/web && npm install && npx next build
cd -
```
Expected: build succeeds (route `/` present).

- [ ] **Step 6: Commit**

```bash
git add apps/interview-demo/web
git commit -m "feat(web): scaffold Next.js app with Start Run page and run-mode selector"
```

---

### Task 25: Progressive artifact tree view

**Files:**
- Create: `apps/interview-demo/web/app/runs/[id]/page.tsx`
- Create: `apps/interview-demo/web/components/ArtifactTree.tsx`

**Interfaces:**
- Consumes: `getRun`, `getRunArtifacts` (Task 24's `lib/api.ts`).
- Produces: a page that polls `GET /runs/:id/artifacts` and renders each artifact as it lands, including per-scene `.mp4` previews.

- [ ] **Step 1: Create `components/ArtifactTree.tsx`**

```tsx
// apps/interview-demo/web/components/ArtifactTree.tsx
"use client";

import { useEffect, useState } from "react";
import { getRunArtifacts } from "@/lib/api";

type ArtifactRow = {
  content_hash: string;
  stage: string;
  scene_id: string | null;
  created_at: string;
};

export function ArtifactTree({ runId }: { runId: string }) {
  const [rows, setRows] = useState<ArtifactRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const data = await getRunArtifacts(runId);
      if (!cancelled) setRows(data as ArtifactRow[]);
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [runId]);

  return (
    <ul>
      {rows.map((row) => (
        <li key={row.content_hash}>
          <strong>{row.stage}</strong>
          {row.scene_id && ` — scene ${row.scene_id}`}
          {(row.stage === "scene_preview" || row.stage === "scene_final") && (
            <video
              src={`/api/artifacts/${row.content_hash}/${row.stage === "scene_preview" ? "preview.mp4" : "scene_final.mp4"}`}
              controls
              width={320}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 2: Create `app/runs/[id]/page.tsx`**

```tsx
// apps/interview-demo/web/app/runs/[id]/page.tsx
import { ArtifactTree } from "@/components/ArtifactTree";

export default function RunPage({ params }: { params: { id: string } }) {
  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Run {params.id}</h1>
      <ArtifactTree runId={params.id} />
    </main>
  );
}
```

- [ ] **Step 3: Confirm it builds**

Run:
```bash
cd apps/interview-demo/web && npx next build
cd -
```
Expected: build succeeds, route `/runs/[id]` present.

- [ ] **Step 4: Commit**

```bash
git add apps/interview-demo/web/app/runs apps/interview-demo/web/components/ArtifactTree.tsx
git commit -m "feat(web): add progressive artifact tree view with per-scene previews"
```

---

### Task 26: Review/edit panel (chat + JSON) and Simulate Crash / Resume buttons

**Files:**
- Create: `apps/interview-demo/web/components/ReviewPanel.tsx`
- Modify: `apps/interview-demo/web/lib/api.ts` (add `postInterruptChat`, `postInterruptResume`, `simulateCrash`)
- Modify: `apps/interview-demo/web/app/runs/[id]/page.tsx` (mount `ReviewPanel` and crash/resume buttons)

**Interfaces:**
- Consumes: `POST /runs/:id/interrupt/chat`, `POST /runs/:id/interrupt/resume`, `POST /runs/:id/simulate-crash`, `POST /runs/:id/resume` (Tasks 22-23).

- [ ] **Step 1: Extend `lib/api.ts`**

```ts
// apps/interview-demo/web/lib/api.ts (append)
export async function postInterruptChat(runId: string, artifactType: string, currentArtifact: Record<string, unknown>, message: string, history: Array<Record<string, unknown>>) {
  const res = await fetch(`${API_BASE}/runs/${runId}/interrupt/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ artifact_type: artifactType, current_artifact: currentArtifact, message, history }),
  });
  if (!res.ok) throw new Error(`interrupt/chat failed: ${res.status}`);
  return res.json();
}

export async function postInterruptResume(runId: string, payload: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/runs/${runId}/interrupt/resume`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`interrupt/resume failed: ${res.status}`);
  return res.json();
}

export async function simulateCrash(runId: string) {
  await fetch(`${API_BASE}/runs/${runId}/simulate-crash`, { method: "POST" });
}

export async function resumeRun(runId: string) {
  const res = await fetch(`${API_BASE}/runs/${runId}/resume`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action: "approve" }),
  });
  if (!res.ok) throw new Error(`resume failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Create `components/ReviewPanel.tsx`**

```tsx
// apps/interview-demo/web/components/ReviewPanel.tsx
"use client";

import { useState } from "react";
import { postInterruptChat, postInterruptResume } from "@/lib/api";

export function ReviewPanel({
  runId,
  artifactType,
  currentArtifact,
}: {
  runId: string;
  artifactType: "Script" | "SceneGraph";
  currentArtifact: Record<string, unknown>;
}) {
  const [artifact, setArtifact] = useState(currentArtifact);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [jsonDraft, setJsonDraft] = useState(JSON.stringify(currentArtifact, null, 2));

  async function sendChatEdit() {
    const { proposed_artifact } = await postInterruptChat(runId, artifactType, artifact, message, history);
    setArtifact(proposed_artifact);
    setJsonDraft(JSON.stringify(proposed_artifact, null, 2));
    setHistory([...history, { role: "user", content: message }, { role: "assistant", content: JSON.stringify(proposed_artifact) }]);
    setMessage("");
  }

  async function approve() {
    await postInterruptResume(runId, { action: "approve" });
  }

  async function submitEditedJson() {
    await postInterruptResume(runId, { action: "edit", artifact: JSON.parse(jsonDraft) });
  }

  return (
    <div style={{ display: "flex", gap: 24 }}>
      <div style={{ flex: 1 }}>
        <h3>Chat ({artifactType})</h3>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g. make scene 3 shorter" rows={3} style={{ width: "100%" }} />
        <button onClick={sendChatEdit}>Send</button>
        <button onClick={approve}>Approve as-is</button>
      </div>
      <div style={{ flex: 1 }}>
        <h3>Raw JSON (editable)</h3>
        <textarea value={jsonDraft} onChange={(e) => setJsonDraft(e.target.value)} rows={20} style={{ width: "100%" }} />
        <button onClick={submitEditedJson}>Submit edited JSON</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Mount the review panel and crash/resume buttons on the run page**

```tsx
// apps/interview-demo/web/app/runs/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { ArtifactTree } from "@/components/ArtifactTree";
import { ReviewPanel } from "@/components/ReviewPanel";
import { getRun, simulateCrash, resumeRun } from "@/lib/api";

export default function RunPage({ params }: { params: { id: string } }) {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => setStatus(await getRun(params.id)), 2000);
    return () => clearInterval(interval);
  }, [params.id]);

  const interrupted = status?.result && (status.result as Record<string, unknown>).__interrupt__;

  return (
    <main style={{ maxWidth: 1000, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Run {params.id}</h1>
      <button onClick={() => simulateCrash(params.id)}>Simulate Crash</button>
      <button onClick={() => resumeRun(params.id)}>Resume</button>
      {interrupted != null && (
        <ReviewPanel
          runId={params.id}
          artifactType="Script"
          currentArtifact={(status!.result as Record<string, unknown>).script as Record<string, unknown>}
        />
      )}
      <ArtifactTree runId={params.id} />
    </main>
  );
}
```

- [ ] **Step 4: Confirm it builds**

Run:
```bash
cd apps/interview-demo/web && npx next build
cd -
```
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/interview-demo/web/components/ReviewPanel.tsx apps/interview-demo/web/lib/api.ts \
        apps/interview-demo/web/app/runs/\[id\]/page.tsx
git commit -m "feat(web): add chat+JSON review panel and simulate-crash/resume controls"
```

---

### Task 27: CLAUDE.md update + end-to-end verification checklist

**Files:**
- Modify: `CLAUDE.md`
- Create: `docs/superpowers/plans/2026-07-03-local-pipeline-verification.md`

**Interfaces:**
- None — documentation and a manual verification pass over everything built in Tasks 1-26.

- [ ] **Step 1: Update `CLAUDE.md`**

Change:
```markdown
## Stack
- Python: LangGraph, sympy, Manim, ffmpeg-python
- TypeScript/Node: Remotion
- Frontend: Next.js (apps/interview-demo)
- Local DB: SQLite (checkpointer + artifact metadata)
```
to:
```markdown
## Stack
- Python: LangGraph, sympy, Manim, ffmpeg (via subprocess)
- TypeScript/Node: Remotion
- Frontend: Next.js (apps/interview-demo)
- Local DB: Postgres via docker-compose (checkpointer + artifact metadata)
```

And append a new subsection after "## Key architectural rules":
```markdown
## Extension seams (for the later GCP-deployment plan)
- `ArtifactStore` (packages/core/src/spectacle_core/artifacts.py) has one
  local-filesystem implementation today; a GCS-backed implementation is a
  drop-in second implementation of the same protocol, not a rewrite.
- `render_scene` (packages/core/src/spectacle_core/nodes/render_scene.py)
  dispatches in-process today; a Cloud Tasks-backed dispatch is meant to
  reuse the same `interrupt()`/`Command(resume=...)` primitive the human
  review steps already use, machine-triggered instead of human-triggered.
```

- [ ] **Step 2: Write the verification checklist**

```markdown
# Local Pipeline — Manual Verification Checklist

Run once after Task 27, in order, against the fully-built local system
(`docker compose up -d`, both `uvicorn` and `npm run dev` running, real
LLM calls wired into the `default_*_llm` seams left as `NotImplementedError`
stubs in Tasks 8/10/23 -- wire up a real client before this pass, or run
against the fake_llm fixtures used in tests for a dry run of the mechanics).

- [ ] **Claim 1 (content-addressed, selective regen):** Run a lesson to
      completion. Note the `worked_example` scene's `scene_input_hash`
      from `GET /runs/:id/artifacts`. Start a second run with the exact
      same spec. Confirm via server logs / artifact timestamps that
      `render_scene` hit the cache-skip branch (Task 17) instead of
      re-rendering.
- [ ] **Claim 2 (kill/resume):** Start a run in `accept_edits` mode. After
      it pauses at Interrupt A, hit "Simulate Crash." Restart `uvicorn`.
      Hit "Resume." Confirm the run continues past Interrupt A rather than
      restarting from `load_spec`.
- [ ] **Claim 3 (human interrupt, Command(resume=...)):** Same run as
      above -- confirm the pause/resume round-trip works via both the
      "Approve as-is" button and a raw-JSON edit submission.
- [ ] **Claim 4 (independent sympy verification):** Edit a Script artifact
      at Interrupt A via the raw JSON panel so the `worked_example` scene's
      `stated_answer` is wrong (e.g. `"1/2"` instead of `"7/8"`). Confirm
      the run halts at `verification_gate` with a `VerificationBlockedError`
      detail visible, and does not proceed to rendering.
- [ ] **Claim 5 (renderer routing):** Confirm `GET /runs/:id/artifacts`
      shows the `worked_example`/`guided_practice` scenes routed to
      `manim` and all others to `remotion`, and that overriding a tag at
      Interrupt B (via chat: "switch the recap scene to Manim") changes
      which renderer actually runs for that scene.
- [ ] **Claim 6 (editable artifacts, selective hash invalidation):** After
      a full run, restart with the same spec but edit one scene's text at
      Interrupt A via chat. Confirm only that scene re-renders (new
      `scene_input_hash`, new render work) while a sibling scene's
      `SceneFinal` artifact is reused unchanged (same hash, no new render
      logged).
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/superpowers/plans/2026-07-03-local-pipeline-verification.md
git commit -m "docs: update CLAUDE.md for Postgres, note GCP extension seams, add verification checklist"
```

---

## Explicitly deferred (separate future plan)

GCP deployment (Cloud Run for `api`/`web`, Cloud SQL for Postgres, GCS for
the `ArtifactStore`, Cloud Tasks for async per-scene render dispatch reusing
the `interrupt()`/`Command(resume=...)` primitive) is **not** part of this
plan. The seams above (`ArtifactStore` protocol, in-process `render_scene`
dispatch) exist specifically so that plan can add a second implementation
of each without touching anything built here.
