"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

type Props = {
  empty: boolean;
};

export function RefreshButton({ empty }: Props) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const autoStarted = useRef(false);

  async function runRefresh() {
    setBusy(true);
    setError(null);
    setStatus("Starting gather…");
    try {
      const start = await fetch("/api/refresh", { method: "POST" });
      const startBody = await start.json();
      if (!start.ok) {
        throw new Error(startBody.error || startBody.detail || "Refresh failed");
      }
      const jobId = startBody.job_id as string;
      setStatus(`Job ${jobId.slice(0, 8)}… running`);

      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const poll = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
        const job = await poll.json();
        if (!poll.ok) {
          throw new Error(job.error || "Poll failed");
        }
        if (job.status === "done") {
          setStatus("Done — reloading insights");
          startTransition(() => router.refresh());
          setBusy(false);
          setStatus(null);
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error || "Gather job failed");
        }
        setStatus(`Gathering… (${job.status})`);
      }
      throw new Error("Timed out waiting for gather");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
      setStatus(null);
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!empty || autoStarted.current) return;
    autoStarted.current = true;
    void runRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empty]);

  return (
    <div className="refresh-row">
      <button type="button" onClick={() => void runRefresh()} disabled={busy || pending}>
        {busy || pending ? "Refreshing…" : "Refresh insights"}
      </button>
      {status ? <span className="caption status-live">{status}</span> : null}
      {error ? <span className="error-text">{error}</span> : null}
    </div>
  );
}
