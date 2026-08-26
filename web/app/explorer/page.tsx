import Link from "next/link";
import { Suspense } from "react";
import { ExplorerSearch } from "@/components/ExplorerSearch";
import { CORPUS_CAPTION, fetchUnits, sourceLabel } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ExplorerPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; source?: string; stance?: string }>;
}) {
  const sp = await searchParams;
  const q = sp.q || "";
  let data = null;
  let error: string | null = null;
  try {
    data = await fetchUnits({
      q: q || undefined,
      source: sp.source,
      stance: sp.stance,
      limit: 50,
    });
  } catch (err) {
    error = err instanceof Error ? err.message : "API error";
  }

  return (
    <>
      <h1>Evidence explorer</h1>
      <p className="caption">Audit trail of coded conversations (not a replacement for home cards).</p>

      <Suspense fallback={null}>
        <ExplorerSearch initialQ={q} />
      </Suspense>

      {error ? (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      ) : null}

      {data ? (
        <>
          <p className="caption">{data.total} matching units</p>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Source</th>
                <th>Stance</th>
                <th>Barrier</th>
                <th>Snippet</th>
              </tr>
            </thead>
            <tbody>
              {data.units.map((u) => (
                <tr key={u.id}>
                  <td className="nowrap">
                    {u.created_at
                      ? new Date(u.created_at).toLocaleDateString()
                      : "—"}
                  </td>
                  <td>{sourceLabel(u.source)}</td>
                  <td>{u.outcome_stance}</td>
                  <td>
                    <Link href={`/behaviors/${encodeURIComponent(u.behavior_id)}`}>
                      {u.behavior_title}
                    </Link>
                  </td>
                  <td>
                    <Link href={`/explorer/${u.id}`} className="snippet-link">
                      {u.snippet}
                    </Link>
                  </td>
                </tr>
              ))}
              {!data.units.length ? (
                <tr>
                  <td colSpan={5}>No units match.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
          <p className="caption footer-caption">{CORPUS_CAPTION}</p>
        </>
      ) : null}
    </>
  );
}
