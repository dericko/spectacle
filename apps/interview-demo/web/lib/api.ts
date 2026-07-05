// apps/interview-demo/web/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type RunMode = "accept_edits" | "auto";

export async function startRun(spec: Record<string, unknown>, runMode: RunMode): Promise<{ run_id: string }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ spec, run_mode: runMode }),
  });
  if (!res.ok) throw new Error(`start run failed: ${res.status}`);
  return res.json();
}

export async function getRun(runId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/runs/${runId}`);
  if (!res.ok) throw new Error(`get run failed: ${res.status}`);
  return res.json();
}

export async function getRunArtifacts(runId: string): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${API_BASE}/runs/${runId}/artifacts`);
  if (!res.ok) throw new Error(`get artifacts failed: ${res.status}`);
  return res.json();
}

export async function postInterruptChat(runId: string, artifactType: string, currentArtifact: Record<string, unknown>, message: string, history: Array<Record<string, unknown>>) {
  const res = await fetch(`${API_BASE}/runs/${runId}/interrupt/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ artifact_type: artifactType, current_artifact: currentArtifact, message, history }),
  });
  if (!res.ok) throw new Error(`interrupt/chat failed: ${res.status}`);
  return res.json();
}

export async function postInterruptResume(runId: string, payload: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/runs/${runId}/interrupt/resume`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`interrupt/resume failed: ${res.status}`);
  return res.json();
}

export async function simulateCrash(runId: string) {
  await fetch(`${API_BASE}/runs/${runId}/simulate-crash`, { method: "POST" });
}

export async function resumeRun(runId: string) {
  const res = await fetch(`${API_BASE}/runs/${runId}/resume`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action: "approve" }),
  });
  if (!res.ok) throw new Error(`resume failed: ${res.status}`);
  return res.json();
}
