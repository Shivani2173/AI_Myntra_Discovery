import Link from "next/link";
import { notFound } from "next/navigation";
import { DownloadButtons } from "@/components/DownloadButtons";
import { CORPUS_CAPTION, fetchBehavior, sourceLabel } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BehaviorDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let b;
  try {
    b = await fetchBehavior(id);
  } catch {
    notFound();
  }

  const analyzed = b.header?.analyzed ?? b.n;
  const quotes = b.quotes || [];
  const levers = b.levers || [];
  const often = b.often_with || [];

  return (
    <>
      <p className="caption">
        <Link href="/">← Home</Link>
      </p>
      <h1>{b.title}</h1>
      <p className="pct">
        {b.didnt_buy_pct}% didn’t buy for this · {b.n} of {analyzed} · {b.voices} voices
      </p>
      <p className="meta-line">
        Stage: {b.w2p_stage} · Intensity {b.intensity}/5
        {b.emergent ? " · Emergent theme" : ""}
      </p>

      <div className="kpis">
        <span>
          postpone {b.stance_mix.postpone}% · abandon {b.stance_mix.abandon}% · bookmark{" "}
          {b.stance_mix.bookmark_only}%
        </span>
        {Object.entries(b.source_mix || {}).map(([src, pct]) => (
          <span key={src}>
            {sourceLabel(src)} {pct}%
          </span>
        ))}
      </div>

      <h2>Behavior</h2>
      <p>{b.mechanism}</p>

      <h2>What we heard</h2>
      {quotes.length ? (
        <ul className="quotes">
          {quotes.map((q) => (
            <li key={`${q.unit_id}-${q.text.slice(0, 40)}`}>
              “{q.text}”
              {q.source ? (
                <span className="caption"> — {sourceLabel(q.source)}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="caption">No quotes stored for this behavior yet.</p>
      )}

      <DownloadButtons behavior={b} />

      <h2>Often with</h2>
      {often.length ? (
        <ul className="overlap-list">
          {often.map((o) => (
            <li key={o.id}>
              <Link href={`/behaviors/${encodeURIComponent(o.id)}`}>{o.title}</Link>
              <span className="caption"> {o.overlap_pct}% overlap</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="caption">No secondary co-occurrence in this sample.</p>
      )}

      <h2>Possible levers</h2>
      <ul>
        {levers.map((L) => (
          <li key={L}>{L}</li>
        ))}
      </ul>

      <p className="caption footer-caption">{CORPUS_CAPTION}</p>
    </>
  );
}
