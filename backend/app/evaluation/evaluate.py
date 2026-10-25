"""CLI: evaluate exported RepoLens retrieval/chat runs from JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.evaluation.metrics import EvaluationDataError, evaluate_rows


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise EvaluationDataError(
                        f"{path}:{line_number}: invalid JSON: {exc.msg}"
                    ) from exc
                if not isinstance(row, dict):
                    raise EvaluationDataError(f"{path}:{line_number}: expected a JSON object.")
                rows.append(row)
    except OSError as exc:
        raise EvaluationDataError(f"Cannot read evaluation input: {exc}") from exc
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSONL export with retrieval and reviewed citation fields")
    parser.add_argument("--output", type=Path, help="Optional path for the JSON report (defaults to stdout)")
    parser.add_argument("--k", type=int, default=5, help="Retrieval cutoff (1–20; default: 5)")
    args = parser.parse_args(argv)
    try:
        report = evaluate_rows(load_jsonl(args.input), k=args.k)
        output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
            print(f"Evaluation report written to {args.output}")
        else:
            sys.stdout.write(output)
    except (EvaluationDataError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
