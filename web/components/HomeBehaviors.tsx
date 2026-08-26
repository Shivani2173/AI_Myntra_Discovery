"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ShareBars } from "@/components/ShareBars";
import { sourceLabel } from "@/lib/api";
import type { BehaviorCard, BehaviorsHeader } from "@/lib/types";

/** Chip id → behavior ids that count as a match for that preset. */
const CHIP_MATCH: Record<string, string[]> = {
  bookmark_inspiration: [
    "bookmark_inspiration",
    "bookmark_compare_later",
    "gift_or_other_person",
    "low_urgency_maybe",
  ],
  fit_size_uncertainty: [
    "fit_size_uncertainty",
    "looks_vs_reality",
    "styling_wardrobe_fit",
  ],
  wait_for_price_drop: [
    "wait_for_price_drop",
    "better_price_elsewhere",
    "budget_payday",
    "value_doubt",
  ],
  oos_after_wishlist: ["oos_after_wishlist", "delivery_too_slow", "forgotten_wishlist"],
  too_many_shortlisted: [
    "too_many_shortlisted",
    "missing_compare_tools",
    "switched_to_alternative",
  ],
  seeking_external_proof: ["seeking_external_proof", "social_validation", "review_trust"],
  forgotten_wishlist: ["forgotten_wishlist"],
};

type Props = {
  header: BehaviorsHeader;
  behaviors: BehaviorCard[];
};

export function HomeBehaviors({ header, behaviors }: Props) {
  const [activeChip, setActiveChip] = useState<string | null>(null);
  const chips = header.chips || [];
  const stance = header.stance_mix;

  const filtered = useMemo(() => {
    if (!activeChip) return behaviors;
    const allowed = new Set(CHIP_MATCH[activeChip] || [activeChip]);
    return behaviors.filter((b) => allowed.has(b.id));
  }, [activeChip, behaviors]);

  return (
    <>
      <div className="kpis">
        <span>
          Analyzed: <strong>{header.analyzed}</strong> · {header.voices} unique voices
        </span>
        {stance ? (
          <span>
            bookmark {stance.bookmark_only}% · postpone {stance.postpone}% · abandon{" "}
            {stance.abandon}%
          </span>
        ) : null}
        {(header.source_status || [])
          .filter((s) => s.source !== "extract" && s.status === "ok")
          .map((s) => (
            <span key={s.source} className={`pill status-${s.status}`}>
              {sourceLabel(s.source)} {s.status}
            </span>
          ))}
      </div>

      <div className="chips" role="group" aria-label="Behavior filters">
        <button
          type="button"
          className={`chip ${activeChip === null ? "chip-active" : ""}`}
          onClick={() => setActiveChip(null)}
        >
          All
        </button>
        {chips.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`chip ${activeChip === c.id ? "chip-active" : ""}`}
            onClick={() => setActiveChip(activeChip === c.id ? null : c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <ShareBars behaviors={filtered.length ? filtered : behaviors} />

      <section className="card-list" aria-label="Behavior cards">
        {filtered.length ? (
          filtered.map((b, i) => (
            <Link
              key={b.id}
              href={`/behaviors/${encodeURIComponent(b.id)}`}
              className="card-link"
            >
              <article className="card">
                <div className="card-top">
                  <span className="rank">{i + 1}</span>
                  <div className="pct">{b.didnt_buy_pct}% didn’t buy</div>
                </div>
                <h2>{b.title}</h2>
                <p className="mechanism">{b.mechanism}</p>
                <p className="caption">
                  {b.n} / {header.analyzed} · {b.voices} voices · postpone{" "}
                  {b.stance_mix.postpone}% · abandon {b.stance_mix.abandon}% · bookmark{" "}
                  {b.stance_mix.bookmark_only}%
                </p>
                <p className="caption">
                  Intensity {b.intensity}/5
                  {b.often_with?.length
                    ? ` · Often with: ${b.often_with
                        .map((o) => `${o.title} ${o.overlap_pct}%`)
                        .join(", ")}`
                    : ""}
                </p>
                <div className="source-mix">
                  {Object.entries(b.source_mix || {}).map(([src, pct]) => (
                    <span key={src}>
                      {sourceLabel(src)} {pct}%
                    </span>
                  ))}
                </div>
              </article>
            </Link>
          ))
        ) : (
          <div className="empty-state">
            <p>No cards match this filter in the current dataset.</p>
            <button type="button" className="btn-secondary" onClick={() => setActiveChip(null)}>
              Show all
            </button>
          </div>
        )}
      </section>
    </>
  );
}
