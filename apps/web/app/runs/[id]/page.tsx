"use client";

import { useEffect, useState } from "react";
import { ArtifactTree } from "@/components/ArtifactTree";
import { ReviewPanel } from "@/components/ReviewPanel";
import { Nav } from "@/components/Nav";
import { getRun, simulateCrash, resumeRun } from "@/lib/api";

export default function RunPage({ params }: { params: { id: string } }) {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const interval = setInterval(
      async () => setStatus(await getRun(params.id)),
      2000
    );
    return () => clearInterval(interval);
  }, [params.id]);

  const result = status?.result as Record<string, unknown> | undefined;
  const interrupted = Boolean(result?.__interrupt__);
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
        {interrupted && (
          <div style={{ marginBottom: 40 }}>
            <ReviewPanel
              runId={params.id}
              artifactType="Script"
              currentArtifact={(result?.script as Record<string, unknown>) ?? {}}
            />
          </div>
        )}

        {/* Pipeline + artifacts */}
        <ArtifactTree runId={params.id} />
      </main>
    </>
  );
}
