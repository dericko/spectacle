"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startRun, RunMode } from "@/lib/api";

export default function StartRunPage() {
  const router = useRouter();
  const [learningObjective, setLearningObjective] = useState("Add fractions with unlike denominators");
  const [expression, setExpression] = useState("3/4 + 1/8");
  const [minutes, setMinutes] = useState(3);
  const [runMode, setRunMode] = useState<RunMode>("accept_edits");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { run_id } = await startRun(
        {
          learning_objective: learningObjective,
          worked_example_expression: expression,
          target_duration_minutes: minutes,
          audience: "6th grade",
        },
        runMode
      );
      router.push(`/runs/${run_id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Start a lesson</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Learning objective
          <input value={learningObjective} onChange={(e) => setLearningObjective(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Worked example expression
          <input value={expression} onChange={(e) => setExpression(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Duration (minutes, 1-10)
          <input type="number" min={1} max={10} value={minutes}
                 onChange={(e) => setMinutes(Number(e.target.value))} />
        </label>
        <fieldset>
          <legend>Run mode</legend>
          <label>
            <input type="radio" checked={runMode === "accept_edits"} onChange={() => setRunMode("accept_edits")} />
            accept_edits (pause for review)
          </label>
          <label>
            <input type="radio" checked={runMode === "auto"} onChange={() => setRunMode("auto")} />
            auto (hands-off)
          </label>
        </fieldset>
        <button type="submit" disabled={submitting}>{submitting ? "Starting..." : "Start Run"}</button>
      </form>
    </main>
  );
}
