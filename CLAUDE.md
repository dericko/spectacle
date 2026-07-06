# Spectacle — Claude Code context

## What this is
A spec-driven, agent-orchestrated video generation pipeline. A lesson/content
spec flows through a LangGraph graph, producing content-addressed artifacts at
each stage, and is rendered to MP4 via Remotion (layout/typography scenes) and
Manim (equation-morphing scenes), muxed with FFmpeg.

## Repo layout
- `packages/core/` — genre-agnostic engine. No domain-specific imports.
- `domains/education/` — education domain pack: spec schema, structure agent,
  sympy verification gate, safety profile.
- `apps/interview-demo/` — Next.js app wiring UI shell to education domain pack.
- `artifacts/` — gitignored local render outputs (content-addressed by hash).

## Key architectural rules
1. Core never imports from domains/. Domain packs plug in via a fixed interface:
   spec_schema / structure(spec) -> ContentTree / verification_gates(scene) /
   safety_profile.
2. Every pipeline stage writes a content-addressed JSON artifact before
   proceeding. Re-runs skip stages whose input hash hasn't changed.
3. Human-in-the-loop interrupts carry editable artifacts back into the graph
   via Command(resume={...}), not bare booleans.
4. Renderer routing is decided by the scene planner agent and is
   human-overridable in the review UI.

## Extension seams (for the later GCP-deployment plan)
- `ArtifactStore` (packages/core/src/spectacle_core/artifacts.py) has one
  local-filesystem implementation today; a GCS-backed implementation is a
  drop-in second implementation of the same protocol, not a rewrite.
- `render_scene` (packages/core/src/spectacle_core/nodes/render_scene.py)
  dispatches in-process today; a Cloud Tasks-backed dispatch is meant to
  reuse the same `interrupt()`/`Command(resume=...)` primitive the human
  review steps already use, machine-triggered instead of human-triggered.

## Stack
- Python: LangGraph, sympy, Manim, ffmpeg (via subprocess)
- TypeScript/Node: Remotion
- Frontend: Next.js (apps/interview-demo)
- Local DB: Postgres via docker-compose (checkpointer + artifact metadata)

## What not to do
- Don't add domain-specific branches inside packages/core/
- Don't build a plugin registry or dynamic loader for domain packs
- Don't regenerate end-to-end when only one scene's input changed
