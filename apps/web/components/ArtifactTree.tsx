"use client";

import { useEffect, useState } from "react";
import { artifactFileUrl, getArtifact } from "@/lib/api";
import { ArtifactPreview } from "@/components/ArtifactPreview";

type ArtifactRow = {
  content_hash: string;
  stage: string;
  scene_id: string | null;
  created_at: string;
};

const PIPELINE_STAGES = [
  { key: "content_tree", label: "structure", desc: "Spec → content tree" },
  { key: "script", label: "script", desc: "Scene narration" },
  { key: "scene_graph", label: "scene_graph", desc: "Renderer routing" },
  { key: "scene_final", label: "render", desc: "Manim · Remotion" },
  { key: "mux", label: "mux", desc: "FFmpeg assembly" },
];

const VIDEO_STAGES = new Set(["scene_preview", "scene_final"]);

function ExpandedArtifact({
  row,
  onClose,
}: {
  row: ArtifactRow;
  onClose: () => void;
}) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    getArtifact(row.content_hash)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [row.content_hash]);

  const panelStyle = {
    background: "var(--surface)",
    border: "1px solid var(--border-bright)",
    borderTop: "none",
    borderRadius: "0 0 var(--radius) var(--radius)",
    padding: "16px 16px 14px",
  };

  const headerStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  };

  const labelStyle = {
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "var(--text-dim)",
    fontFamily: "var(--font-mono), monospace",
  };

  const closeBtn = {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "var(--text-dim)",
    fontSize: 16,
    lineHeight: 1,
    padding: "0 2px",
  };

  if (VIDEO_STAGES.has(row.stage)) {
    const filename = row.stage === "scene_preview" ? "preview.mp4" : "scene_final.mp4";
    return (
      <div style={panelStyle}>
        <div style={headerStyle}>
          <span style={labelStyle}>Preview</span>
          <button onClick={onClose} style={closeBtn} aria-label="Close">×</button>
        </div>
        <video
          src={artifactFileUrl(row.content_hash, filename)}
          controls
          style={{ width: "100%", borderRadius: 4, background: "#000", display: "block" }}
        />
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={labelStyle}>Preview</span>
        <button onClick={onClose} style={closeBtn} aria-label="Close">×</button>
      </div>

      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}

      {!data && !error && (
        <div style={{ color: "var(--text-dim)", fontSize: 13 }}>Loading…</div>
      )}

      {data && <ArtifactPreview stage={row.stage} data={data} />}
    </div>
  );
}

export function ArtifactTree({ runId, rows }: { runId: string; rows: ArtifactRow[] }) {
  const [selectedHash, setSelectedHash] = useState<string | null>(null);

  const doneStages = new Set(rows.map((r) => r.stage));

  const lastDoneIndex = PIPELINE_STAGES.reduce(
    (acc, s, i) => (doneStages.has(s.key) ? i : acc),
    -1
  );
  const activeIndex =
    lastDoneIndex < PIPELINE_STAGES.length - 1 ? lastDoneIndex + 1 : -1;

  const muxRow = rows.find((r) => r.stage === "mux");
  const logRows = rows.filter((r) => r.stage !== "mux");

  function toggleRow(hash: string) {
    setSelectedHash((prev) => (prev === hash ? null : hash));
  }

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

      {/* Final video */}
      {muxRow && (
        <div>
          <p className="field-label" style={{ marginBottom: 12 }}>
            Final video
          </p>
          <div className="card" style={{ padding: "14px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <span className="mono" style={{ color: "var(--text-muted)" }}>mux</span>
              <span className="hash" style={{ marginLeft: "auto" }}>
                {muxRow.content_hash.slice(0, 12)}
              </span>
            </div>
            <video
              src={artifactFileUrl(muxRow.content_hash, "final.mp4")}
              controls
              style={{ width: "100%", borderRadius: 4, background: "#000", display: "block" }}
            />
          </div>
        </div>
      )}

      {/* Artifact log */}
      {logRows.length > 0 && (
        <div>
          <p className="field-label" style={{ marginBottom: 10 }}>
            Artifacts
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {logRows.map((row) => {
              const isSelected = selectedHash === row.content_hash;
              return (
                <div key={`${row.content_hash}-${row.stage}`}>
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleRow(row.content_hash)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") toggleRow(row.content_hash);
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 12px",
                      background: isSelected ? "var(--surface-2)" : "var(--surface)",
                      border: "1px solid var(--border)",
                      borderBottom: isSelected
                        ? "1px solid var(--border-bright)"
                        : "1px solid var(--border)",
                      borderRadius: isSelected
                        ? "var(--radius) var(--radius) 0 0"
                        : "var(--radius)",
                      cursor: "pointer",
                      userSelect: "none",
                      transition: "background 0.1s",
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected)
                        (e.currentTarget as HTMLElement).style.background = "var(--surface-2)";
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected)
                        (e.currentTarget as HTMLElement).style.background = "var(--surface)";
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        color: "var(--text-dim)",
                        transition: "transform 0.15s",
                        display: "inline-block",
                        transform: isSelected ? "rotate(90deg)" : "rotate(0deg)",
                      }}
                    >
                      ▶
                    </span>
                    <span className="dot" />
                    <span className="mono" style={{ color: "var(--text-muted)" }}>
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

                  {isSelected && (
                    <ExpandedArtifact
                      row={row}
                      onClose={() => setSelectedHash(null)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {rows.length === 0 && (
        <div style={{ padding: "32px 0", color: "var(--text-dim)", fontSize: 13 }}>
          Waiting for pipeline to start…
        </div>
      )}
    </div>
  );
}
