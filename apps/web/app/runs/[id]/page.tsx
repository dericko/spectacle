"use client";

import { useEffect, useState } from "react";
import { ArtifactTree } from "@/components/ArtifactTree";
import { ReviewPanel } from "@/components/ReviewPanel";
import { Nav } from "@/components/Nav";
import { streamRun, simulateCrash, resumeRun } from "@/lib/api";

type ArtifactRow = {
  content_hash: string;
  stage: string;
  scene_id: string | null;
  created_at: string;
};

export default function RunPage({ params }: { params: { id: string } }) {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRow[]>([]);

  useEffect(() => {
    const stop = streamRun(params.id, ({ status: s, artifacts: a }) => {
      if (s) setStatus(s);
      if (a) setArtifacts(a as ArtifactRow[]);
    });
    return stop;
  }, [params.id]);

  const result = status?.result as Record<string, unknown> | undefined;
  const interrupted = Boolean(result?.__interrupt__);
  // Scene graph review comes after script review; detect by whether scene_graph is in state.
  const interruptType = interrupted && result?.scene_graph ? "SceneGraph" : "Script";
  const interruptArtifact =
    (interruptType === "SceneGraph"
      ? result?.scene_graph
      : result?.script) as Record<string, unknown> | undefined;

  const shortId = params.id.length > 8 ? `${params.id.slice(0, 8)}…` : params.id;

  return (
    <>
      <Nav crumb={{ label: shortId }} />

      <main style={{ padding: "32px 24px 96px", maxWidth: 1100, margin: "0 auto" }}>
        {/* Run header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 32,
            flexWrap: "wrap",
          }}
        >
          <div>
            <p className="field-label" style={{ marginBottom: 4 }}>
              Run ID
            </p>
            <span
              className="mono display"
              style={{ fontSize: 16, letterSpacing: "0.02em", color: "var(--text)" }}
            >
              {params.id}
            </span>
          </div>

          {status && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontFamily: "var(--font-mono), monospace",
                fontSize: 11,
                fontWeight: 500,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                padding: "3px 10px",
                borderRadius: 99,
                ...(interrupted
                  ? {
                      background: "var(--amber-dim)",
                      border: "1px solid var(--amber-border)",
                      color: "var(--amber)",
                    }
                  : {
                      background: "var(--surface-2)",
                      border: "1px solid var(--border-bright)",
                      color: "var(--text-muted)",
                    }),
              }}
            >
              {interrupted ? (
                <>
                  <span
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: "var(--amber)",
                      display: "inline-block",
                    }}
                  />
                  awaiting review
                </>
              ) : (
                String(status.status ?? "running")
              )}
            </span>
          )}

          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button
              className="btn btn-secondary"
              onClick={() => simulateCrash(params.id)}
            >
              Simulate crash
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => resumeRun(params.id)}
            >
              Resume
            </button>
          </div>
        </div>

        {/* Review panel — shown prominently when interrupted */}
        {interrupted && interruptArtifact && (
          <div style={{ marginBottom: 40 }}>
            <ReviewPanel
              runId={params.id}
              artifactType={interruptType}
              currentArtifact={interruptArtifact}
            />
          </div>
        )}

        {/* Pipeline + artifacts */}
        <ArtifactTree runId={params.id} rows={artifacts} />
      </main>
    </>
  );
}
