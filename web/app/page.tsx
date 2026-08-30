import { HomeBehaviors } from "@/components/HomeBehaviors";
import { RefreshButton } from "@/components/RefreshButton";
import { CORPUS_CAPTION, fetchBehaviors, formatWhen } from "@/lib/api";
import type { BehaviorsResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

async function load(): Promise<{ data: BehaviorsResponse | null; error: string | null }> {
  try {
    const data = await fetchBehaviors();
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Could not reach API",
    };
  }
}

export default async function HomePage() {
  const { data, error } = await load();
  const empty = !data || (data.header.analyzed === 0 && data.behaviors.length === 0);
  const header = data?.header;
  const behaviors = data?.behaviors || [];

  return (
    <>
      <header className="page-head">
        <h1>Why they didn’t buy from wishlist</h1>
        <RefreshButton empty={empty && !error} />
      </header>

      {error ? (
        <div className="banner banner-error" role="alert">
          API unreachable: {error}. Start the backend (`uvicorn backend.main:app --reload --port
          8000`) and set <code>NEXT_PUBLIC_API_URL</code>.
        </div>
      ) : null}

      {empty && !error ? (
        <div className="empty-state">
          <p>No coded conversations yet. Auto-refresh will try to gather if the DB is empty.</p>
          <p className="caption">
            Or run locally: <code>python -m backend.cli gather</code>
          </p>
        </div>
      ) : null}

      {header && !empty ? (
        <>
          <p className="caption">Last coded: {formatWhen(header.last_coded_at)}</p>
          <HomeBehaviors header={header} behaviors={behaviors} />
        </>
      ) : null}

      <p className="caption footer-caption">{CORPUS_CAPTION}</p>
    </>
  );
}
