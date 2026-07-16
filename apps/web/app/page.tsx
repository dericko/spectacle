"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
  const [rawInput, setRawInput] = useState(
    "Teach a 6th grade class how to add fractions with unlike denominators, using 3/4 + 1/8 as a worked example. Keep it to about 3 minutes."
  );
  const [runMode, setRunMode] = useState<RunMode>("accept_edits");
  const [stubLlm, setStubLlm] = useState(false);
  const [isDebug, setIsDebug] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsDebug(new URLSearchParams(window.location.search).get("debug") === "true");
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { run_id } = await startRun(rawInput, runMode, stubLlm);
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
            <p style={{ color: "var(--text-muted)", fontSize: 15, maxWidth: 520, lineHeight: 1.6, marginBottom: 16 }}>
              Spectacle orchestrates structure, script, rendering, and mux through
              a LangGraph pipeline — and hands you an MP4.
            </p>
            <Link href="/library" style={{ fontSize: 13, color: "var(--teal)", textDecoration: "none" }}>
              View past runs →
            </Link>
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
                  <label className="field-label" htmlFor="raw-input">
                    Describe the lesson
                  </label>
                  <textarea
                    id="raw-input"
                    className="field-input"
                    value={rawInput}
                    onChange={(e) => setRawInput(e.target.value)}
                    placeholder="e.g. Teach a 6th grade class how to add fractions with unlike denominators, using 3/4 + 1/8 as a worked example. Keep it to about 3 minutes."
                    rows={6}
                    style={{ resize: "vertical", lineHeight: 1.55 }}
                    required
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

                {isDebug && (
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 12,
                      color: "var(--text-muted)",
                      padding: "8px 10px",
                      background: "var(--surface-2)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius)",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={stubLlm}
                      onChange={(e) => setStubLlm(e.target.checked)}
                      style={{ accentColor: "var(--amber)" }}
                    />
                    <span>
                      <span style={{ fontFamily: "var(--font-mono), monospace", fontWeight: 600 }}>
                        Stub LLM calls
                      </span>
                      {" "}— skip all API calls, use placeholder text
                    </span>
                  </label>
                )}

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
