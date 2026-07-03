# Spectacle

AI video generation pipeline POC. Spec-driven, agent-orchestrated,
content-addressed.

Monorepo structure:
- `packages/core` — genre-agnostic engine: graph orchestration, artifact
  store, renderer routing, FFmpeg mux, review/edit UI shell
- `domains/` — domain packs (currently: `education`)
- `apps/` — runnable apps (currently: `interview-demo`)
- `artifacts/` — local render outputs (gitignored)
