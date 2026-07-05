// apps/interview-demo/web/app/runs/[id]/page.tsx
import { ArtifactTree } from "@/components/ArtifactTree";

export default function RunPage({ params }: { params: { id: string } }) {
  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Run {params.id}</h1>
      <ArtifactTree runId={params.id} />
    </main>
  );
}
