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
