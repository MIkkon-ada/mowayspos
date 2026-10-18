"""Read-only report for legacy key-task assignees that lack person IDs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

# Make the backend package importable when invoked as `python scripts/...py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional explicit output path for a row-level manual-review CSV.",
    )
    args = parser.parse_args()

    from app.database import SessionLocal
    from app.services.task_assignee_audit import audit_unbound_task_assignees

    with SessionLocal() as db:
        rows = audit_unbound_task_assignees(db)

    counts = Counter(row["classification"] for row in rows)
    print(json.dumps({"total": len(rows), **dict(counts)}, ensure_ascii=False, indent=2))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        columns = [
            "subtask_id", "project_id", "project_name", "workstream_id",
            "workstream_name", "title", "assignee_name", "classification",
            "candidate_person_ids",
        ]
        with args.csv.open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    **row,
                    "candidate_person_ids": ",".join(map(str, row["candidate_person_ids"])),
                })
        print(f"CSV written: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
