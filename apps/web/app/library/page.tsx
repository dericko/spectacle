"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { listRuns } from "@/lib/api";

type Run = { run_id: string; name: string; status: string; created_at: string };

const STATUS_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  running: { label: "Running", color: "var(--teal)", bg: "var(--teal-dim)" },
  paused:  { label: "Awaiting review", color: "var(--text-muted)", bg: "var(--surface-2)" },
  done:    { label: "Done", color: "var(--green)", bg: "var(--green-dim)" },
  error:   { label: "Error", color: "var(--red)", bg: "var(--red-dim)" },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? { label: status, color: "var(--text-muted)", bg: "var(--surface-2)" };
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 5,
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
      color: s.color,
      background: s.bg,
      padding: "3px 8px",
      borderRadius: "var(--radius)",
    }}>
      {status === "running" && (
        <span style={{
          width: 6, height: 6, borderRadius: "50%",
          background: "var(--teal)", flexShrink: 0,
          animation: "node-pulse 1.8s ease-in-out infinite",
        }} />
      )}
      {s.label}
    </span>
  );
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

export default function LibraryPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <Nav crumb={{ label: "Library" }} />
      <main style={{ padding: "48px 24px 96px" }}>
        <div style={{ maxWidth: 800, margin: "0 auto" }}>
          <div style={{ marginBottom: 32 }}>
            <h1 className="display" style={{ fontSize: 28, letterSpacing: "-0.03em", marginBottom: 6 }}>
              Library
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
              All generated videos, newest first.
            </p>
          </div>

          {error && (
            <div className="alert alert-error" style={{ marginBottom: 24 }}>{error}</div>
          )}

          {runs === null && !error && (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</div>
          )}

          {runs !== null && runs.length === 0 && (
            <div className="card" style={{ padding: 40, textAlign: "center" }}>
              <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 16 }}>
                No runs yet.
              </p>
              <Link href="/" className="btn btn-primary">Start a run</Link>
            </div>
          )}

          {runs !== null && runs.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {runs.map((run, i) => (
                <Link
                  key={run.run_id}
                  href={`/runs/${run.run_id}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto auto",
                    alignItems: "center",
                    gap: 16,
                    padding: "14px 0",
                    borderBottom: i < runs.length - 1 ? "1px solid var(--border)" : "none",
                    textDecoration: "none",
                    color: "inherit",
                    transition: "opacity 0.1s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.7")}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)", marginBottom: 3 }}>
                      {run.name}
                    </div>
                    <div className="hash">{run.run_id.slice(0, 8)}</div>
                  </div>
                  <StatusBadge status={run.status} />
                  <div style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "right", whiteSpace: "nowrap" }}>
                    {formatDate(run.created_at)}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
