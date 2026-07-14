# Spectacle iteration log

---

## Iteration 1 — 2026-07-14

### Goals
- Run pipeline end-to-end and fix obvious bugs
- Test full UI with stub LLM mode (`run_mode: "auto"`, `stub_llm: true`)
- Inspect final video and improve Manim/Remotion animations for K-8 professional quality
- Ensure every video has full audio
- Commit all changes to main

### Bugs fixed

**Critical: Manim scenes missing from final video (silent frame drop)**
- Root cause: FFmpeg concat demuxer silently drops all frames from clips whose `time_base` differs from the first clip. Remotion clips use `time_base=1/90000`; Manim clips use `time_base=1/15360` (Manim's internal clock). Adding `-video_track_timescale 90000` to `mux_audio_video()` in `render_scene.py` normalizes the container timebase without re-encoding.
- File: `packages/core/src/spectacle_core/nodes/render_scene.py`

**Minor: Finalize step lacked output framerate specification**
- Added `-r 30` to the `ffmpeg_concat()` call to force 30fps output.
- File: `packages/core/src/spectacle_core/nodes/finalize.py`

### Visual improvements

**Manim scene redesign (`manim_scene.py`):**
- Added scene-type badge (WORKED EXAMPLE, TRY IT!, etc.) in the header using the same color palette as Remotion
- Added thin top accent bar matching the scene-type color (mirrors the Remotion accent stripe)
- Increased step label font size from 34 → 40 and brightened label color (slate-300 instead of slate-400)
- Grouped label + equation as a VGroup for consistent vertical centering
- Badge/bar colors match Remotion SCENE_META exactly: orange for worked_example, yellow for guided_practice

**Remotion (LayoutScene.tsx) — no changes needed; already at K-8 quality:**
- Navy background (#0b1021), colored scene-type badge, numbered items, sequential entrance animation
- Top accent stripe in scene-type color
- Global fade-out on last 18 frames for clean cuts

### Verified output
- Final video: 2793 frames, 93.1s, h264@30fps
- Scene order: Intro → Concept Explanation → Worked Example (Manim) → Guided Practice (Manim) → Recap
- All 5 scenes present and correctly ordered
- All scenes have audio (MacSay TTS, resampled 22050→44100 Hz)
- Worked example shows 3/4 + 1/8 → 6/8 + 1/8 → 7/8 in 3 animated steps
- Guided practice shows 1/2 + 1/4 with TRY IT! badge in yellow

### README updated
- Added "Renderer design" section covering K-8 design system, scene-type badge table, Remotion/Manim renderer details, and the FFmpeg timebase normalization fix

---
