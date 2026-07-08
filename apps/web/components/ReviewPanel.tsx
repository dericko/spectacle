"use client";

import { useState } from "react";
import { postInterruptChat, postInterruptResume } from "@/lib/api";
import { ArtifactPreview } from "@/components/ArtifactPreview";

type Message = { role: "user" | "assistant"; content: string };

export function ReviewPanel({
  runId,
  artifactType,
  currentArtifact,
}: {
  runId: string;
  artifactType: "Script" | "SceneGraph";
  currentArtifact: Record<string, unknown>;
}) {
  // Panel visibility is driven by the parent (SSE stream) — no local dismiss needed.
  const [artifact, setArtifact] = useState(currentArtifact);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Message[]>([]);
  const [jsonDraft, setJsonDraft] = useState(
    JSON.stringify(currentArtifact, null, 2)
  );
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [approving, setApproving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [tab, setTab] = useState<"chat" | "json">("chat");

  async function sendChatEdit() {
    if (!message.trim()) return;
    setSending(true);
    setError(null);
    try {
      const { proposed_artifact } = await postInterruptChat(
        runId,
        artifactType,
        artifact,
        message,
        history
      );
      const next: Message[] = [
        ...history,
        { role: "user", content: message },
        { role: "assistant", content: JSON.stringify(proposed_artifact) },
      ];
      setArtifact(proposed_artifact);
      setJsonDraft(JSON.stringify(proposed_artifact, null, 2));
      setHistory(next);
      setMessage("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat edit failed.");
    } finally {
      setSending(false);
    }
  }

  async function approve() {
    setApproving(true);
    setError(null);
    try {
      await postInterruptResume(runId, { action: "approve" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed.");
    } finally {
      setApproving(false);
    }
  }

  async function submitEditedJson() {
    setSubmitting(true);
    setError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonDraft);
    } catch {
      setError("Invalid JSON — fix the syntax before submitting.");
      setSubmitting(false);
      return;
    }
    try {
      await postInterruptResume(runId, { action: "edit", artifact: parsed });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      sendChatEdit();
    }
  }

  return (
    <div
      className="card"
      style={{ padding: 0, overflow: "hidden" }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          borderBottom: "1px solid var(--border)",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--amber)",
              display: "inline-block",
              animation: "node-pulse 1.8s ease-in-out infinite",
            }}
          />
          <span
            className="display"
            style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em" }}
          >
            Awaiting review
          </span>
          <span
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              background: "var(--surface-2)",
              padding: "2px 7px",
              borderRadius: 99,
              border: "1px solid var(--border-bright)",
            }}
          >
            {artifactType}
          </span>
        </div>
        <button
          className="btn btn-primary"
          onClick={approve}
          disabled={approving}
          style={{ padding: "6px 14px", fontSize: 13 }}
        >
          {approving ? "Approving…" : "Approve"}
        </button>
      </div>

      {/* Artifact preview */}
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <p
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "var(--text-dim)",
            fontFamily: "var(--font-mono), monospace",
            marginBottom: 10,
          }}
        >
          Preview
        </p>
        <ArtifactPreview
          stage={artifactType === "Script" ? "script" : "scene_graph"}
          data={artifact}
        />
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border)",
          padding: "0 20px",
          gap: 0,
        }}
      >
        {(["chat", "json"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t ? "var(--amber)" : "transparent"}`,
              color: tab === t ? "var(--text)" : "var(--text-muted)",
              font: "inherit",
              fontSize: 13,
              fontWeight: tab === t ? 500 : 400,
              padding: "10px 14px 9px",
              cursor: "pointer",
              transition: "color 0.12s, border-color 0.12s",
              marginBottom: -1,
            }}
          >
            {t === "chat" ? "Chat" : "JSON editor"}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ padding: "20px" }}>
        {tab === "chat" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* History */}
            {history.length > 0 && (
              <div className="chat-history">
                {history.map((msg, i) => (
                  <div
                    key={i}
                    className={`chat-message chat-${msg.role}`}
                  >
                    <span className="chat-role">{msg.role}</span>
                    <span className="chat-content">
                      {msg.role === "assistant"
                        ? "[artifact updated]"
                        : msg.content}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {history.length === 0 && (
              <p style={{ fontSize: 13, color: "var(--text-dim)" }}>
                Describe what to change and the AI will propose an updated artifact.
              </p>
            )}

            {/* Input */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g. make scene 3 shorter, simplify the worked example…"
                rows={3}
                style={{
                  background: "var(--bg)",
                  border: "1px solid var(--border-bright)",
                  borderRadius: "var(--radius)",
                  color: "var(--text)",
                  fontFamily: "var(--font-body), sans-serif",
                  fontSize: 14,
                  padding: "9px 12px",
                  resize: "vertical",
                  outline: "none",
                  width: "100%",
                  lineHeight: 1.55,
                  transition: "border-color 0.12s, box-shadow 0.12s",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "var(--amber-border)";
                  e.target.style.boxShadow = "0 0 0 3px var(--amber-dim)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "var(--border-bright)";
                  e.target.style.boxShadow = "none";
                }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button
                  className="btn btn-secondary"
                  onClick={sendChatEdit}
                  disabled={sending || !message.trim()}
                >
                  {sending ? "Sending…" : "Send"}
                </button>
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                  ⌘↵ to send
                </span>
              </div>
            </div>
          </div>
        )}

        {tab === "json" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
              Edit the artifact directly, then submit to continue the pipeline.
            </p>
            <textarea
              value={jsonDraft}
              onChange={(e) => setJsonDraft(e.target.value)}
              rows={18}
              spellCheck={false}
              style={{
                background: "var(--bg)",
                border: "1px solid var(--border-bright)",
                borderRadius: "var(--radius)",
                color: "var(--text)",
                fontFamily: "var(--font-mono), monospace",
                fontSize: 12,
                padding: "12px",
                resize: "vertical",
                outline: "none",
                width: "100%",
                lineHeight: 1.6,
                transition: "border-color 0.12s, box-shadow 0.12s",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--amber-border)";
                e.target.style.boxShadow = "0 0 0 3px var(--amber-dim)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--border-bright)";
                e.target.style.boxShadow = "none";
              }}
            />
            <button
              className="btn btn-secondary"
              onClick={submitEditedJson}
              disabled={submitting}
              style={{ alignSelf: "flex-start" }}
            >
              {submitting ? "Submitting…" : "Submit edited JSON"}
            </button>
          </div>
        )}

        {error && (
          <div className="alert alert-error" role="alert" style={{ marginTop: 14 }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
