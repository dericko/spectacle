export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
export const API_KEY = process.env.NEXT_PUBLIC_SPECTACLE_API_KEY;

const AUTH_HEADERS: Record<string, string> = API_KEY ? { authorization: `Bearer ${API_KEY}` } : {};

export type RunMode = "accept_edits" | "auto";

export async function listRuns(): Promise<Array<{ run_id: string; name: string; status: string; created_at: string }>> {
  const res = await fetch(`${API_BASE}/runs`, { headers: AUTH_HEADERS });
  if (!res.ok) throw new Error(`list runs failed: ${res.status}`);
  return res.json();
}

export async function startRun(spec: Record<string, unknown>, runMode: RunMode, stubLlm = false): Promise<{ run_id: string }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json", ...AUTH_HEADERS },
    body: JSON.stringify({ spec, run_mode: runMode, stub_llm: stubLlm }),
  });
  if (!res.ok) throw new Error(`start run failed: ${res.status}`);
  return res.json();
}

export async function getRun(runId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/runs/${runId}`, { headers: AUTH_HEADERS });
  if (!res.ok) throw new Error(`get run failed: ${res.status}`);
  return res.json();
}

export async function getRunArtifacts(runId: string): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${API_BASE}/runs/${runId}/artifacts`, { headers: AUTH_HEADERS });
  if (!res.ok) throw new Error(`get artifacts failed: ${res.status}`);
  return res.json();
}

export function artifactFileUrl(contentHash: string, filename: string): string {
  // Plain <video src> / <img src> requests can't set custom headers, so the
  // API key travels as a query param here (see require_api_key / streamRun).
  const url = new URL(`${API_BASE}/api/artifacts/${contentHash}/${filename}`);
  if (API_KEY) url.searchParams.set("api_key", API_KEY);
  return url.toString();
}

export async function getArtifact(contentHash: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/artifacts/${contentHash}`, { headers: AUTH_HEADERS });
  if (!res.ok) throw new Error(`get artifact failed: ${res.status}`);
  return res.json();
}

export async function postInterruptChat(runId: string, artifactType: string, currentArtifact: Record<string, unknown>, message: string, history: Array<Record<string, unknown>>) {
  const res = await fetch(`${API_BASE}/runs/${runId}/interrupt/chat`, {
    method: "POST",
    headers: { "content-type": "application/json", ...AUTH_HEADERS },
    body: JSON.stringify({ artifact_type: artifactType, current_artifact: currentArtifact, message, history }),
  });
  if (!res.ok) throw new Error(`interrupt/chat failed: ${res.status}`);
  return res.json();
}

export async function postInterruptResume(runId: string, payload: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/runs/${runId}/interrupt/resume`, {
    method: "POST",
    headers: { "content-type": "application/json", ...AUTH_HEADERS },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`interrupt/resume failed: ${res.status}`);
  return res.json();
}

export async function simulateCrash(runId: string) {
  await fetch(`${API_BASE}/runs/${runId}/simulate-crash`, { method: "POST", headers: AUTH_HEADERS });
}

export async function resumeRun(runId: string) {
  const res = await fetch(`${API_BASE}/runs/${runId}/resume`, {
    method: "POST",
    headers: { "content-type": "application/json", ...AUTH_HEADERS },
    body: JSON.stringify({ action: "approve" }),
  });
  if (!res.ok) throw new Error(`resume failed: ${res.status}`);
  return res.json();
}

export function streamRun(
  runId: string,
  onEvent: (data: { status: Record<string, unknown> | null; artifacts: Array<Record<string, unknown>> }) => void,
): () => void {
  let source: EventSource | null = null;
  let stopped = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (stopped) return;
    // EventSource cannot set custom headers, so the API key travels as a
    // query param here (the server accepts either form — see require_api_key).
    const url = new URL(`${API_BASE}/runs/${runId}/stream`);
    if (API_KEY) url.searchParams.set("api_key", API_KEY);
    source = new EventSource(url);
    source.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        // ignore malformed events
      }
    };
    source.onerror = () => {
      source?.close();
      source = null;
      if (!stopped) {
        retryTimer = setTimeout(connect, 2000);
      }
    };
  }

  connect();
  return () => {
    stopped = true;
    if (retryTimer) clearTimeout(retryTimer);
    source?.close();
  };
}
