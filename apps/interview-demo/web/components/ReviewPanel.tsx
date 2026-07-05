// apps/interview-demo/web/components/ReviewPanel.tsx
"use client";

import { useState } from "react";
import { postInterruptChat, postInterruptResume } from "@/lib/api";

export function ReviewPanel({
  runId,
  artifactType,
  currentArtifact,
}: {
  runId: string;
  artifactType: "Script" | "SceneGraph";
  currentArtifact: Record<string, unknown>;
}) {
  const [artifact, setArtifact] = useState(currentArtifact);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [jsonDraft, setJsonDraft] = useState(JSON.stringify(currentArtifact, null, 2));

  async function sendChatEdit() {
    const { proposed_artifact } = await postInterruptChat(runId, artifactType, artifact, message, history);
    setArtifact(proposed_artifact);
    setJsonDraft(JSON.stringify(proposed_artifact, null, 2));
    setHistory([...history, { role: "user", content: message }, { role: "assistant", content: JSON.stringify(proposed_artifact) }]);
    setMessage("");
  }

  async function approve() {
    await postInterruptResume(runId, { action: "approve" });
  }

  async function submitEditedJson() {
    await postInterruptResume(runId, { action: "edit", artifact: JSON.parse(jsonDraft) });
  }

  return (
    <div style={{ display: "flex", gap: 24 }}>
      <div style={{ flex: 1 }}>
        <h3>Chat ({artifactType})</h3>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g. make scene 3 shorter" rows={3} style={{ width: "100%" }} />
        <button onClick={sendChatEdit}>Send</button>
        <button onClick={approve}>Approve as-is</button>
      </div>
      <div style={{ flex: 1 }}>
        <h3>Raw JSON (editable)</h3>
        <textarea value={jsonDraft} onChange={(e) => setJsonDraft(e.target.value)} rows={20} style={{ width: "100%" }} />
        <button onClick={submitEditedJson}>Submit edited JSON</button>
      </div>
    </div>
  );
}
