"use client";

import { useEffect, useState } from "react";
import { getRunArtifacts } from "@/lib/api";

type ArtifactRow = {
  content_hash: string;
  stage: string;
  scene_id: string | null;
  created_at: string;
};

const PIPELINE_STAGES = [
  { key: "structure", label: "structure", desc: "Spec → content tree" },
  { key: "script", label: "script", desc: "Scene narration" },
  { key: "scene_graph", label: "scene_graph", desc: "Renderer routing" },
  { key: "scene_preview", label: "render", desc: "Manim · Remotion" },
  { key: "mux", label: "mux", desc: "FFmpeg assembly" },
];

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

  const doneStages = new Set(rows.map((r) => r.stage));

  const lastDoneIndex = PIPELINE_STAGES.reduce(
    (acc, s, i) => (doneStages.has(s.key) ? i : acc),
    -1
  );
  const activeIndex =
    lastDoneIndex < PIPELINE_STAGES.length - 1 ? lastDoneIndex + 1 : -1;

  const videoRows = rows.filter(
    (r) => r.stage === "scene_preview" || r.stage === "scene_final"
  );

  const nonVideoRows = rows.filter(
    (r) => r.stage !== "scene_preview" && r.stage !== "scene_final"
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
      {/* Pipeline timeline */}
      <div>
        <p className="field-label" style={{ marginBottom: 18 }}>
          Pipeline
        </p>
        <div className="pipeline">
          {PIPELINE_STAGES.map((stage, i) => {
            const done = doneStages.has(stage.key);
            const active = i === activeIndex && !done;
            return (
              <div
                key={stage.key}
                className={[
                  "pipeline-stage",
                  done ? "stage-done" : "",
                  active ? "stage-active" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <div className="pipeline-node" />
                <div className="pipeline-info">
                  <div className="pipeline-stage-name">{stage.label}</div>
                  <div className="pipeline-stage-meta">
                    {done ? "complete" : active ? "running…" : stage.desc}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Video previews */}
      {videoRows.length > 0 && (
        <div>
          <p className="field-label" style={{ marginBottom: 12 }}>
            Scene renders
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {videoRows.map((row) => (
              <div
                key={row.content_hash}
                className="card"
                style={{ padding: "14px 16px" }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 10,
                  }}
                >
                  <span className="mono" style={{ color: "var(--text-muted)" }}>
                    {row.stage}
                  </span>
                  {row.scene_id && (
                    <span
                      style={{ color: "var(--text-dim)", fontSize: 12 }}
                    >
                      scene {row.scene_id}
                    </span>
                  )}
                  <span className="hash" style={{ marginLeft: "auto" }}>
                    {row.content_hash.slice(0, 12)}
                  </span>
                </div>
                <video
                  src={`/api/artifacts/${row.content_hash}/${
                    row.stage === "scene_preview"
                      ? "preview.mp4"
                      : "scene_final.mp4"
                  }`}
                  controls
                  style={{
                    width: "100%",
                    borderRadius: 4,
                    background: "#000",
                    display: "block",
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Artifact log */}
      {nonVideoRows.length > 0 && (
        <div>
          <p className="field-label" style={{ marginBottom: 10 }}>
            Artifacts
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {nonVideoRows.map((row) => (
              <div
                key={row.content_hash}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 12px",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                }}
              >
                <span className="dot" />
                <span
                  className="mono"
                  style={{ color: "var(--text-muted)" }}
                >
                  {row.stage}
                </span>
                {row.scene_id && (
                  <span style={{ color: "var(--text-dim)", fontSize: 11 }}>
                    scene {row.scene_id}
                  </span>
                )}
                <span className="hash" style={{ marginLeft: "auto" }}>
                  {row.content_hash.slice(0, 12)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {rows.length === 0 && (
        <div
          style={{
            padding: "32px 0",
            color: "var(--text-dim)",
            fontSize: 13,
          }}
        >
          Waiting for pipeline to start…
        </div>
      )}
    </div>
  );
}
