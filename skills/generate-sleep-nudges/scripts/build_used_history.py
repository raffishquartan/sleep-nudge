"""Compute the rolling 90-day used-stubs and used-URLs sets from entries/*.yaml.

Used by the generate-sleep-nudges skill to dedup against recently-emailed nudges.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml


@dataclass
class UsedHistory:
    stubs: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)


def build_used_history(entries_dir: Path, *, as_of: str, window_days: int = 90) -> UsedHistory:
    """Return the set of stubs and URLs used in the (as_of - window_days, as_of] interval.

    `as_of` is an ISO date string (YYYY-MM-DD). Future-dated entries (date > as_of) are
    excluded from the dedup set so that batch-generation does not see itself.
    GENERATION_FAILED entries contribute their stub but no URLs.
    """
    if not entries_dir.exists():
        return UsedHistory()
    as_of_date = date.fromisoformat(as_of)
    cutoff_date = as_of_date - timedelta(days=window_days)

    used = UsedHistory()
    for path in sorted(entries_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        for date_iso, entry in data.items():
            if not isinstance(entry, dict):
                continue
            try:
                entry_date = date.fromisoformat(date_iso)
            except ValueError:
                continue
            if entry_date > as_of_date:
                continue
            if entry_date <= cutoff_date:
                continue

            stub = entry.get("stub")
            if stub:
                used.stubs.add(stub)

            if entry.get("status") == "GENERATED":
                for ref in entry.get("references") or []:
                    url = ref.get("url") if isinstance(ref, dict) else None
                    if url:
                        used.urls.add(url)
    return used


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries-dir", type=Path, required=True)
    parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date for the 'today' anchor. Default: now() in UTC.",
    )
    parser.add_argument("--window-days", type=int, default=90)
    args = parser.parse_args()

    as_of = args.as_of or datetime.utcnow().strftime("%Y-%m-%d")
    used = build_used_history(args.entries_dir, as_of=as_of, window_days=args.window_days)
    yaml.safe_dump(
        {"stubs": sorted(used.stubs), "urls": sorted(used.urls)},
        sys.stdout,
        default_flow_style=False,
    )


if __name__ == "__main__":
    main()
