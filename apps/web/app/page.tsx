"use client";

import { useEffect, useState } from "react";

type HealthState = "checking" | "ok" | "error";

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<HealthState>("checking");
  const [dbStatus, setDbStatus] = useState<HealthState>("checking");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

    fetch(`${base}/health`)
      .then((r) => (r.ok ? setApiStatus("ok") : setApiStatus("error")))
      .catch(() => setApiStatus("error"));

    fetch(`${base}/health/db`)
      .then((r) => (r.ok ? setDbStatus("ok") : setDbStatus("error")))
      .catch(() => setDbStatus("error"));
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-xl font-semibold text-gray-100">Moneyball — Phase 1 scaffold</h1>
      <p className="mt-2 text-terminal-muted">
        MLB · NBA · AFL · Soccer. Base currency: AUD. No models wired up yet — this
        page just confirms the stack is alive before Phase 2 (data ingestion) starts.
      </p>
      <div className="mt-8 space-y-2 rounded border border-terminal-border bg-terminal-panel p-4">
        <StatusRow label="API" status={apiStatus} />
        <StatusRow label="Database" status={dbStatus} />
      </div>
    </main>
  );
}

function StatusRow({ label, status }: { label: string; status: HealthState }) {
  const color =
    status === "ok" ? "text-terminal-edge" : status === "error" ? "text-terminal-edgeNeg" : "text-terminal-muted";
  const text = status === "ok" ? "OK" : status === "error" ? "UNREACHABLE" : "checking...";
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-300">{label}</span>
      <span className={color}>{text}</span>
    </div>
  );
}
