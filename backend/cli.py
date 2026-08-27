"""CLI: python -m backend.cli health | gather | extract | behaviors | eval"""

import argparse
import json
import sys

from backend.behaviors import rebuild_and_persist
from backend.csv_seed import run_import_csv
from backend.db import init_db, ping_db, session_scope
from backend.extract import run_extract
from backend.gather import run_gather


def cmd_health() -> int:
    init_db()
    ping_db()
    print("ok")
    return 0


def cmd_gather() -> int:
    init_db()
    db = session_scope()
    try:
        print("[cli] gathering sources (Reddit → YouTube → App Store)…", flush=True)
        result = run_gather(db)
        print("[cli] extracting / coding new units…", flush=True)
        result["extract"] = run_extract(db)
        print(json.dumps(result, indent=2))
        return 0
    except KeyboardInterrupt:
        print("\n[cli] stopped (Ctrl+C). Partial source saves may already be in the DB.", flush=True)
        return 130
    finally:
        db.close()


def cmd_import_csv() -> int:
    init_db()
    db = session_scope()
    try:
        result = run_import_csv(db)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        db.close()


def cmd_extract() -> int:
    init_db()
    db = session_scope()
    try:
        result = run_extract(db)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        db.close()


def cmd_behaviors() -> int:
    init_db()
    db = session_scope()
    try:
        result = rebuild_and_persist(db)
        slim = {
            "analyzed": result["header"]["analyzed"],
            "voices": result["header"]["voices"],
            "primary_share_sum": result["primary_share_sum"],
            "caption": result["caption"],
            "behaviors": [
                {
                    "id": b["id"],
                    "didnt_buy_pct": b["didnt_buy_pct"],
                    "n": b["n"],
                    "voices": b["voices"],
                    "intensity": b["intensity"],
                    "title": b["title"],
                }
                for b in result["behaviors"]
            ],
        }
        print(json.dumps(slim, indent=2))
        return 0
    finally:
        db.close()


def cmd_eval(predict: str) -> int:
    from eval.score import main as eval_main

    return eval_main(["--predict", predict])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health", help="Create tables if needed and ping the database")
    sub.add_parser("gather", help="Pull sources into units, then code new rows")
    sub.add_parser("import-csv", help="Import the bundled curated evidence CSV as units (idempotent)")
    sub.add_parser("extract", help="Gemini/Ollama-code uncoded relevant units only")
    sub.add_parser("behaviors", help="Rebuild CPU-only behavior map from stored codes")
    ev = sub.add_parser("eval", help="Gold-set precision/recall")
    ev.add_argument(
        "--predict",
        choices=("db", "stub", "llm"),
        default="stub",
        help="db=stored codes; stub=keyword coder; llm=Gemini/Ollama",
    )
    args = parser.parse_args(argv)
    if args.command == "health":
        return cmd_health()
    if args.command == "gather":
        return cmd_gather()
    if args.command == "import-csv":
        return cmd_import_csv()
    if args.command == "extract":
        return cmd_extract()
    if args.command == "behaviors":
        return cmd_behaviors()
    if args.command == "eval":
        return cmd_eval(args.predict)
    return 1


if __name__ == "__main__":
    sys.exit(main())
