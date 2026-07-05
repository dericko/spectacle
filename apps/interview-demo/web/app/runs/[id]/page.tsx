// apps/interview-demo/web/app/runs/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { ArtifactTree } from "@/components/ArtifactTree";
import { ReviewPanel } from "@/components/ReviewPanel";
import { getRun, simulateCrash, resumeRun } from "@/lib/api";

export default function RunPage({ params }: { params: { id: string } }) {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => setStatus(await getRun(params.id)), 2000);
    return () => clearInterval(interval);
  }, [params.id]);

  const interrupted = status?.result && (status.result as Record<string, unknown>).__interrupt__;

  return (
    <main style={{ maxWidth: 1000, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Run {params.id}</h1>
      <button onClick={() => simulateCrash(params.id)}>Simulate Crash</button>
      <button onClick={() => resumeRun(params.id)}>Resume</button>
      {interrupted != null && (
        <ReviewPanel
          runId={params.id}
          artifactType="Script"
          currentArtifact={((status!.result as Record<string, unknown>).script as Record<string, unknown>) ?? {}}
        />
      )}
      <ArtifactTree runId={params.id} />
    </main>
  );
}
