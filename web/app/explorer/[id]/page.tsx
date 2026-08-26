import Link from "next/link";
import { notFound } from "next/navigation";
import { CORPUS_CAPTION, fetchUnit, sourceLabel } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function UnitDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const num = Number(id);
  if (!Number.isFinite(num)) notFound();

  let unit;
  try {
    unit = await fetchUnit(num);
  } catch {
    notFound();
  }

  const code = unit.code || {};

  return (
    <>
      <p className="caption">
        <Link href="/explorer">← Explorer</Link>
      </p>
      <h1>Unit #{unit.id}</h1>
      <div className="kpis">
        <span>{sourceLabel(unit.source)}</span>
        <span>{String(code.outcome_stance || "—")}</span>
        <span>{String(code.primary_barrier || "—")}</span>
        {unit.url ? (
          <a href={unit.url} target="_blank" rel="noreferrer">
            Source link
          </a>
        ) : null}
      </div>
      <h2>Full text</h2>
      <pre className="unit-text">{unit.text}</pre>
      <h2>Model code</h2>
      <pre className="unit-text">{JSON.stringify(code, null, 2)}</pre>
      <p className="caption footer-caption">{CORPUS_CAPTION}</p>
    </>
  );
}
