"""Score gold labels vs model codes (DB) or a live/stub predictor.

Usage:
  python -m eval.score                  # compare gold ↔ codes in DATABASE_URL
  python -m eval.score --predict stub   # run StubClient on gold texts (CI-friendly)
  python -m eval.score --predict llm    # run configured Gemini/Ollama on gold texts
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import init_db, session_scope
from backend.llm import StubClient, resolve_client
from backend.models import Code, Unit
from backend.config import get_settings
from backend.relevance import is_relevant
from backend.store import content_hash

GOLD_PATH = Path(__file__).resolve().parent / "gold_set.jsonl"


def load_gold(path: Path = GOLD_PATH) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _metrics(pairs: list[tuple[object, object]]) -> dict:
    """pairs of (gold, pred). For multi-class: accuracy + micro P/R via exact match counts."""
    if not pairs:
        return {"n": 0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    correct = sum(1 for g, p in pairs if g == p)
    # One-vs-rest micro for labels that appear in gold
    labels = sorted({g for g, _ in pairs})
    tp = fp = fn = 0
    for label in labels:
        for g, p in pairs:
            if p == label and g == label:
                tp += 1
            elif p == label and g != label:
                fp += 1
            elif p != label and g == label:
                fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "n": len(pairs),
        "accuracy": round(correct / len(pairs), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _bool_metrics(pairs: list[tuple[bool, bool]]) -> dict:
    if not pairs:
        return {"n": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "accuracy": 0.0}
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if (not g) and p)
    fn = sum(1 for g, p in pairs if g and (not p))
    tn = sum(1 for g, p in pairs if (not g) and (not p))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "n": len(pairs),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round((tp + tn) / len(pairs), 4),
    }


def predict_stub(text: str) -> dict:
    raw = StubClient().complete(text, None)
    return json.loads(raw)


def predict_llm(text: str) -> dict:
    settings = get_settings()
    client = resolve_client(settings)
    if client is None:
        raise RuntimeError("No LLM configured (set GEMINI_API_KEY or run Ollama)")
    from backend.llm import parse_extracted

    return parse_extracted(client.complete(text, None)).model_dump(mode="json")


def predictions_from_db(gold: list[dict]) -> list[dict | None]:
    init_db()
    db = session_scope()
    out: list[dict | None] = []
    try:
        for row in gold:
            h = content_hash(row["text"])
            unit = db.scalar(select(Unit).where(Unit.content_hash == h).limit(1))
            if unit is None:
                # fallback: exact text match
                unit = db.scalar(select(Unit).where(Unit.text == row["text"]).limit(1))
            if unit is None:
                out.append(None)
                continue
            code = db.scalar(select(Code).where(Code.unit_id == unit.id))
            if code is None or not isinstance(code.payload, dict):
                out.append(None)
                continue
            out.append(dict(code.payload))
    finally:
        db.close()
    return out


def score(gold: list[dict], preds: list[dict | None]) -> dict:
    rel_pairs: list[tuple[bool, bool]] = []
    stance_pairs: list[tuple[str, str]] = []
    barrier_pairs: list[tuple[str, str]] = []
    missing = 0
    confusion = Counter()

    for g, p in zip(gold, preds):
        if p is None:
            missing += 1
            continue
        g_rel = bool(g.get("relevant"))
        # Prefer explicit relevant flag; else cheap filter if model omitted
        if "relevant" in p:
            p_rel = bool(p.get("relevant"))
        else:
            p_rel = is_relevant(g["text"])
        rel_pairs.append((g_rel, p_rel))

        if not g_rel:
            continue  # stance/barrier only scored on relevant gold

        g_stance = str(g.get("outcome_stance") or "")
        p_stance = str(p.get("outcome_stance") or "")
        g_bar = str(g.get("primary_barrier") or "")
        p_bar = str(p.get("primary_barrier") or "")
        stance_pairs.append((g_stance, p_stance))
        barrier_pairs.append((g_bar, p_bar))
        if g_bar != p_bar:
            confusion[f"{g_bar}→{p_bar}"] += 1

    report = {
        "gold_n": len(gold),
        "scored_n": len(gold) - missing,
        "missing_predictions": missing,
        "relevance": _bool_metrics(rel_pairs),
        "outcome_stance": _metrics(stance_pairs),
        "primary_barrier": _metrics(barrier_pairs),
        "barrier_confusions_top": confusion.most_common(10),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gold-set precision/recall")
    parser.add_argument(
        "--predict",
        choices=("db", "stub", "llm"),
        default="db",
        help="db=match stored codes; stub=keyword StubClient; llm=Gemini/Ollama",
    )
    parser.add_argument("--gold", type=Path, default=GOLD_PATH)
    args = parser.parse_args(argv)

    gold = load_gold(args.gold)
    if not gold:
        print("gold set empty", file=sys.stderr)
        return 1

    if args.predict == "db":
        preds = predictions_from_db(gold)
    elif args.predict == "stub":
        preds = []
        for row in gold:
            try:
                preds.append(predict_stub(row["text"]))
            except Exception:
                preds.append(None)
    else:
        preds = []
        for row in gold:
            try:
                preds.append(predict_llm(row["text"]))
            except Exception as exc:
                print(f"llm fail {row.get('id')}: {exc}", file=sys.stderr)
                preds.append(None)

    report = score(gold, preds)
    print(json.dumps(report, indent=2))
    # Soft gate for CI stub mode: relevance should be decent
    if args.predict == "stub" and report["relevance"]["f1"] < 0.5:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
