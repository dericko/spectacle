"use client";

// ── type shapes matching the Python models ──────────────────────────────────

type SceneStub = {
  scene_id: string;
  render_hint: string;
  content_hint: string;
  target_duration_s: number;
  verify?: boolean;
  expression?: string | null;
};

type ContentTree = {
  spec_hash: string;
  scenes: SceneStub[];
  schema_version?: string;
};

type SceneNarration = {
  scene_id: string;
  render_hint: string;
  narration_text: string;
  on_screen_text: string;
  target_duration_s: number;
  verify?: boolean;
  expression?: string | null;
  stated_answer?: string | null;
};

type Script = {
  node_version?: string;
  tree_hash?: string;
  scenes: SceneNarration[];
};

type SceneGraphEntry = {
  scene_id: string;
  renderer: string;
  narration_text: string;
  on_screen_text: string;
  target_duration_s: number;
  verify?: boolean;
  expression?: string | null;
  stated_answer?: string | null;
  render_params?: Record<string, unknown>;
};

type SceneGraph = {
  node_version?: string;
  script_hash?: string;
  scenes: SceneGraphEntry[];
};

// ── helpers ─────────────────────────────────────────────────────────────────

function dur(s: number) {
  return `${s}s`;
}

function Badge({ label, color }: { label: string; color?: string }) {
  return (
    <span
      style={{
        fontFamily: "var(--font-mono), monospace",
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        padding: "2px 6px",
        borderRadius: 4,
        background: color ?? "var(--surface-2)",
        border: "1px solid var(--border-bright)",
        color: color ? "#000" : "var(--text-muted)",
        flexShrink: 0,
      }}
    >
      {label}
    </span>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--text-dim)",
          fontFamily: "var(--font-mono), monospace",
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
        {value}
      </span>
    </div>
  );
}

function SceneCard({ children, id }: { children: React.ReactNode; id: string }) {
  return (
    <div
      style={{
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--text-dim)",
          fontFamily: "var(--font-mono), monospace",
          letterSpacing: "0.04em",
        }}
      >
        scene {id}
      </span>
      {children}
    </div>
  );
}

// ── per-stage renderers ──────────────────────────────────────────────────────

function StructurePreview({ data }: { data: ContentTree }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Field label="Scenes" value={String(data.scenes.length)} />
        {data.spec_hash && (
          <Field label="Spec hash" value={data.spec_hash.slice(0, 12) + "…"} />
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {data.scenes.map((s) => (
          <SceneCard key={s.scene_id} id={s.scene_id}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, flexWrap: "wrap" }}>
              <Badge label={s.render_hint} />
              <Badge label={dur(s.target_duration_s)} />
              {s.verify && <Badge label="verify" color="var(--amber)" />}
            </div>
            <Field label="Content hint" value={s.content_hint} />
            {s.expression && <Field label="Expression" value={s.expression} />}
          </SceneCard>
        ))}
      </div>
    </div>
  );
}

function ScriptPreview({ data }: { data: Script }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <Field label="Scenes" value={String(data.scenes.length)} />
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {data.scenes.map((s) => (
          <SceneCard key={s.scene_id} id={s.scene_id}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Badge label={s.render_hint} />
              <Badge label={dur(s.target_duration_s)} />
              {s.verify && <Badge label="verify" color="var(--amber)" />}
            </div>
            <Field label="Narration" value={s.narration_text} />
            <Field label="On-screen" value={s.on_screen_text} />
            {s.expression && <Field label="Expression" value={s.expression} />}
            {s.stated_answer && <Field label="Stated answer" value={s.stated_answer} />}
          </SceneCard>
        ))}
      </div>
    </div>
  );
}

function SceneGraphPreview({ data }: { data: SceneGraph }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <Field label="Scenes" value={String(data.scenes.length)} />
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {data.scenes.map((s) => (
          <SceneCard key={s.scene_id} id={s.scene_id}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Badge
                label={s.renderer}
                color={s.renderer === "manim" ? "#d4edda" : "#cce5ff"}
              />
              <Badge label={dur(s.target_duration_s)} />
              {s.verify && <Badge label="verify" color="var(--amber)" />}
            </div>
            <Field label="Narration" value={s.narration_text} />
            <Field label="On-screen" value={s.on_screen_text} />
            {s.expression && <Field label="Expression" value={s.expression} />}
            {s.stated_answer && <Field label="Stated answer" value={s.stated_answer} />}
            {s.render_params && Object.keys(s.render_params).length > 0 && (
              <Field
                label="Render params"
                value={JSON.stringify(s.render_params, null, 2)}
              />
            )}
          </SceneCard>
        ))}
      </div>
    </div>
  );
}

function GenericPreview({ data }: { data: Record<string, unknown> }) {
  return (
    <pre
      style={{
        margin: 0,
        padding: "12px 14px",
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        fontFamily: "var(--font-mono), monospace",
        fontSize: 12,
        lineHeight: 1.65,
        color: "var(--text)",
        overflowX: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

// ── main export ──────────────────────────────────────────────────────────────

export function ArtifactPreview({
  stage,
  data,
}: {
  stage: string;
  data: Record<string, unknown>;
}) {
  if (stage === "structure" && Array.isArray((data as ContentTree).scenes)) {
    return <StructurePreview data={data as ContentTree} />;
  }
  if (
    (stage === "script" || stage === "script_review") &&
    Array.isArray((data as Script).scenes) &&
    (data as Script).scenes[0] &&
    "narration_text" in ((data as Script).scenes[0] ?? {})
  ) {
    return <ScriptPreview data={data as Script} />;
  }
  if (
    (stage === "scene_graph" || stage === "scene_graph_review") &&
    Array.isArray((data as SceneGraph).scenes) &&
    (data as SceneGraph).scenes[0] &&
    "renderer" in ((data as SceneGraph).scenes[0] ?? {})
  ) {
    return <SceneGraphPreview data={data as SceneGraph} />;
  }
  return <GenericPreview data={data} />;
}
