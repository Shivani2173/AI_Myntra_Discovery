import type { BehaviorCard } from "@/lib/types";

type Props = {
  behaviors: BehaviorCard[];
};

export function ShareBars({ behaviors }: Props) {
  if (!behaviors.length) return null;
  const max = Math.max(...behaviors.map((b) => b.didnt_buy_pct), 1);
  return (
    <section className="share-bars" aria-label="Primary barrier shares">
      <p className="caption">
        Primary reason share (% of analyzed conversations — bars sum to ~100%)
      </p>
      <ul>
        {behaviors.map((b) => (
          <li key={b.id}>
            <span className="bar-label" title={b.title}>
              {b.title}
            </span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{ width: `${(b.didnt_buy_pct / max) * 100}%` }}
              />
            </div>
            <span className="bar-pct">{b.didnt_buy_pct}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
