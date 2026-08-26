from __future__ import annotations

import json
from pathlib import Path

from eval.score import load_gold, score


def test_gold_set_size_and_schema():
    path = Path(__file__).resolve().parent.parent / "eval" / "gold_set.jsonl"
    if not path.exists() or path.read_text(encoding="utf-8").strip().startswith('{"note"'):
        from eval.build_gold_set import main as build

        build()
    rows = load_gold(path)
    assert 80 <= len(rows) <= 150
    for row in rows[:5]:
        assert "text" in row and "relevant" in row
        assert "outcome_stance" in row and "primary_barrier" in row


def test_score_perfect_predictions():
    gold = [
        {
            "id": "1",
            "text": "wishlist size",
            "relevant": True,
            "outcome_stance": "postpone",
            "primary_barrier": "fit_size_uncertainty",
        },
        {
            "id": "2",
            "text": "weather",
            "relevant": False,
            "outcome_stance": "unclear",
            "primary_barrier": "other_offtopic",
        },
    ]
    preds = [
        {
            "relevant": True,
            "outcome_stance": "postpone",
            "primary_barrier": "fit_size_uncertainty",
        },
        {"relevant": False, "outcome_stance": "unclear", "primary_barrier": "other_offtopic"},
    ]
    report = score(gold, preds)
    assert report["relevance"]["f1"] == 1.0
    assert report["primary_barrier"]["accuracy"] == 1.0
    assert report["missing_predictions"] == 0


def test_stub_eval_runs():
    from eval.score import main

    code = main(["--predict", "stub"])
    assert code == 0
