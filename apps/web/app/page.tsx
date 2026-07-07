"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startRun, RunMode } from "@/lib/api";
import { Nav } from "@/components/Nav";

const PIPELINE_STAGES = [
  { label: "structure", desc: "Spec → content tree" },
  { label: "script", desc: "Scene-by-scene narration" },
  { label: "scene_graph", desc: "Renderer routing" },
  { label: "render", desc: "Manim · Remotion" },
  { label: "mux", desc: "FFmpeg assembly" },
];

export default function StartRunPage() {
  const router = useRouter();
  const [learningObjective, setLearningObjective] = useState(
    "Add fractions with unlike denominators"
  );
  const [expression, setExpression] = useState("3/4 + 1/8");
  const [minutes, setMinutes] = useState(3);
  const [runMode, setRunMode] = useState<RunMode>("accept_edits");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start run.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Nav />
      <main style={{ padding: "56px 24px 96px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>

          {/* Hero */}
          <div style={{ marginBottom: 52 }}>
            <h1
              className="display"
              style={{
                fontSize: 38,
                lineHeight: 1.12,
                letterSpacing: "-0.03em",
                marginBottom: 12,
                color: "var(--text)",
              }}
            >
              Turn a spec into a video.
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: 15, maxWidth: 520, lineHeight: 1.6 }}>
              Spectacle orchestrates structure, script, rendering, and mux through
              a LangGraph pipeline — and hands you an MP4.
            </p>
          </div>

          {/* Two column */}
          <div
            className="two-col"
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 280px",
              gap: 32,
              alignItems: "start",
            }}
          >
            {/* Form */}
            <div className="card" style={{ padding: 28 }}>
              <form
                onSubmit={handleSubmit}
                style={{ display: "flex", flexDirection: "column", gap: 22 }}
              >
                <div className="field">
                  <label className="field-label" htmlFor="objective">
                    Learning objective
                  </label>
                  <input
                    id="objective"
                    className="field-input"
                    value={learningObjective}
                    onChange={(e) => setLearningObjective(e.target.value)}
                    placeholder="e.g. Add fractions with unlike denominators"
                    required
                  />
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="expression">
                    Worked example
                  </label>
                  <input
                    id="expression"
                    className="field-input field-input-mono"
                    value={expression}
                    onChange={(e) => setExpression(e.target.value)}
                    placeholder="e.g. 3/4 + 1/8"
                    required
                  />
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="duration">
                    Duration (minutes)
                  </label>
                  <input
                    id="duration"
                    className="field-input"
                    type="number"
                    min={1}
                    max={10}
                    value={minutes}
                    onChange={(e) => setMinutes(Number(e.target.value))}
                    style={{ width: 100 }}
                  />
                </div>

                <div className="field">
                  <span className="field-label">Run mode</span>
                  <div className="radio-group">
                    <label className="radio-option">
                      <input
                        type="radio"
                        name="runMode"
                        checked={runMode === "accept_edits"}
                        onChange={() => setRunMode("accept_edits")}
                      />
                      <div>
                        <div className="radio-label">Guided</div>
                        <div className="radio-desc">Pause for review</div>
                      </div>
                    </label>
                    <label className="radio-option">
                      <input
                        type="radio"
                        name="runMode"
                        checked={runMode === "auto"}
                        onChange={() => setRunMode("auto")}
                      />
                      <div>
                        <div className="radio-label">Autonomous</div>
                        <div className="radio-desc">Run end-to-end</div>
                      </div>
                    </label>
                  </div>
                </div>

                {error && (
                  <div className="alert alert-error" role="alert">
                    {error}
                  </div>
                )}

                <div style={{ paddingTop: 2 }}>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? "Starting…" : "Generate video"}
                  </button>
                </div>
              </form>
            </div>

            {/* Pipeline diagram */}
            <div>
              <p className="field-label" style={{ marginBottom: 18 }}>
                Pipeline
              </p>
              <div className="pipeline">
                {PIPELINE_STAGES.map((stage) => (
                  <div key={stage.label} className="pipeline-stage">
                    <div className="pipeline-node" />
                    <div className="pipeline-info">
                      <div className="pipeline-stage-name">{stage.label}</div>
                      <div className="pipeline-stage-meta">{stage.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
