"use client";

import type { BehaviorCard } from "@/lib/types";

function csvEscape(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

export function DownloadButtons({ behavior }: { behavior: BehaviorCard }) {
  function downloadQuotes() {
    const lines = (behavior.quotes || []).map((q) => `• ${q.text}`);
    const blob = new Blob(
      [`${behavior.title}\n\nWhat we heard\n\n${lines.join("\n")}\n`],
      { type: "text/plain;charset=utf-8" },
    );
    trigger(blob, `${behavior.id}-quotes.txt`);
  }

  function downloadCsv() {
    const header = ["quote", "source", "unit_id", "confidence", "url"];
    const rows = (behavior.quotes || []).map((q) =>
      [
        csvEscape(q.text || ""),
        csvEscape(q.source || ""),
        String(q.unit_id ?? ""),
        String(q.confidence ?? ""),
        csvEscape(q.url || ""),
      ].join(","),
    );
    const blob = new Blob([[header.join(","), ...rows].join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    trigger(blob, `${behavior.id}-quotes.csv`);
  }

  function trigger(blob: Blob, name: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="download-row">
      <button type="button" className="btn-secondary" onClick={downloadQuotes}>
        Download quotes
      </button>
      <button type="button" className="btn-secondary" onClick={downloadCsv}>
        Download CSV
      </button>
    </div>
  );
}
