"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

export function ExplorerSearch({ initialQ }: { initialQ: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const [q, setQ] = useState(initialQ);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams(params.toString());
    if (q.trim()) next.set("q", q.trim());
    else next.delete("q");
    next.delete("offset");
    router.push(`/explorer?${next.toString()}`);
  }

  return (
    <form className="explorer-search" onSubmit={onSubmit}>
      <input
        type="search"
        name="q"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search quotes, barriers, text…"
        aria-label="Search units"
      />
      <button type="submit">Search</button>
    </form>
  );
}
