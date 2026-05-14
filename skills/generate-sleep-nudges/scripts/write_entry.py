"""Atomically merge a single dated entry into entries/YYYY-MM.yaml.

Validates the entry against the schema for its declared status, then performs:
  load file -> set entry[date_iso] = entry -> write to a temp file in the same dir ->
  fsync -> rename onto the destination.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

VALID_STATUSES = {"GENERATED", "GENERATION_FAILED"}
GENERATED_REQUIRED = {"status", "category", "stub", "subject", "body"}
FAILED_REQUIRED = {"status", "category", "stub", "failure_reason"}


class EntryValidationError(ValueError):
    pass


def validate_entry(date_iso: str, entry: dict) -> None:
    try:
        date.fromisoformat(date_iso)
    except ValueError as e:
        raise EntryValidationError(f"invalid date_iso {date_iso!r}: {e}") from e

    status = entry.get("status")
    if status not in VALID_STATUSES:
        raise EntryValidationError(
            f"invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}"
        )

    if status == "GENERATED":
        missing = GENERATED_REQUIRED - set(entry)
        if missing:
            raise EntryValidationError(
                f"GENERATED entry missing required fields: {sorted(missing)}"
            )
    else:
        missing = FAILED_REQUIRED - set(entry)
        if missing:
            raise EntryValidationError(
                f"GENERATION_FAILED entry missing required fields: {sorted(missing)}"
            )


def write_entry(entries_dir: Path, date_iso: str, entry: dict) -> Path:
    validate_entry(date_iso, entry)
    entries_dir.mkdir(parents=True, exist_ok=True)
    month = date_iso[:7]
    target = entries_dir / f"{month}.yaml"

    if target.exists():
        existing = yaml.safe_load(target.read_text()) or {}
    else:
        existing = {}

    existing[date_iso] = entry

    ordered = {k: existing[k] for k in sorted(existing.keys())}
    payload = yaml.safe_dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True)

    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(payload)
    os.replace(tmp, target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries-dir", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument(
        "--entry-json",
        required=True,
        help="JSON-encoded entry dict matching the schema for its status.",
    )
    args = parser.parse_args()

    entry = json.loads(args.entry_json)
    try:
        path = write_entry(args.entries_dir, args.date, entry)
    except EntryValidationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"Wrote {args.date} into {path}")


if __name__ == "__main__":
    main()
