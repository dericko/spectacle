"use client";

import { useEffect, useState } from "react";
import { getRunArtifacts } from "@/lib/api";

type ArtifactRow = {
  content_hash: string;
  stage: string;
  scene_id: string | null;
  created_at: string;
};

export function ArtifactTree({ runId }: { runId: string }) {
  const [rows, setRows] = useState<ArtifactRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const data = await getRunArtifacts(runId);
      if (!cancelled) setRows(data as ArtifactRow[]);
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [runId]);

  return (
    <ul>
      {rows.map((row) => (
        <li key={row.content_hash}>
          <strong>{row.stage}</strong>
          {row.scene_id && ` — scene ${row.scene_id}`}
          {(row.stage === "scene_preview" || row.stage === "scene_final") && (
            <video
              src={`/api/artifacts/${row.content_hash}/${row.stage === "scene_preview" ? "preview.mp4" : "scene_final.mp4"}`}
              controls
              width={320}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
