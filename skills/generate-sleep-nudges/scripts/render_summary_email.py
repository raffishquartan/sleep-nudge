"""Render a TL;DR + rich summary email for a generated sleep-nudge batch.

The TL;DR is a bullet list of `YYYY-MM-DD | category | stub`. The rich body lists each
entry's references and flags:
  [NEW]    - the cited paper was published_at within the last 90 days vs `as_of`.
  [FIRST]  - this URL has not appeared in any earlier-dated entry in entries/*.yaml.
  [FAILED] - the entry is GENERATION_FAILED; the failure_reason is included.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml


def _load_all_entries(entries_dir: Path) -> dict[str, dict]:
    if not entries_dir.exists():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(entries_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        for date_iso, entry in data.items():
            if isinstance(entry, dict):
                out[date_iso] = entry
    return out


def _published_within(published_at: str | None, *, as_of: date, days: int) -> bool:
    if not published_at:
        return False
    pub_str = str(published_at)
    try:
        if len(pub_str) == 4:
            pub_date = date(int(pub_str), 1, 1)
        elif len(pub_str) == 7:
            year, month = pub_str.split("-")
            pub_date = date(int(year), int(month), 1)
        else:
            pub_date = date.fromisoformat(pub_str)
    except (ValueError, TypeError):
        return False
    return (as_of - pub_date) <= timedelta(days=days)


def _first_use(url: str, target_date_iso: str, all_entries: dict[str, dict]) -> bool:
    """True if `target_date_iso` is the earliest date at which this URL appears."""
    for date_iso in sorted(all_entries.keys()):
        if date_iso >= target_date_iso:
            break
        entry = all_entries[date_iso]
        for ref in entry.get("references") or []:
            if isinstance(ref, dict) and ref.get("url") == url:
                return False
    return True


def render_summary(entries_dir: Path, *, start: str, end: str, as_of: str) -> str:
    all_entries = _load_all_entries(entries_dir)
    as_of_date = date.fromisoformat(as_of)

    in_range = sorted(d for d in all_entries if start <= d <= end)
    generated = [d for d in in_range if all_entries[d].get("status") == "GENERATED"]
    failed = [d for d in in_range if all_entries[d].get("status") == "GENERATION_FAILED"]

    lines: list[str] = []
    lines.append(f"Sleep Nudge generation summary {start}..{end}")
    lines.append("")
    lines.append(f"Generated: {len(generated)}")
    lines.append(f"Failed: {len(failed)}")
    lines.append("")
    lines.append("== TL;DR ==")
    if not in_range:
        lines.append("(none)")
    for date_iso in in_range:
        entry = all_entries[date_iso]
        flag = " [FAILED]" if entry.get("status") == "GENERATION_FAILED" else ""
        lines.append(
            f"- {date_iso} | {entry.get('category', '?')} | {entry.get('stub', '?')}{flag}"
        )
    lines.append("")
    lines.append("== Detail ==")

    for date_iso in in_range:
        entry = all_entries[date_iso]
        lines.append("")
        lines.append(f"--- {date_iso} ---")
        lines.append(f"Category: {entry.get('category', '?')}")
        lines.append(f"Stub: {entry.get('stub', '?')}")
        lines.append(f"Subject: {entry.get('subject', '(none)')}")
        if entry.get("status") == "GENERATION_FAILED":
            lines.append(f"[FAILED] reason: {entry.get('failure_reason', '?')}")
            continue
        refs = entry.get("references") or []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            url = ref.get("url", "")
            tags = []
            if _published_within(ref.get("published_at"), as_of=as_of_date, days=90):
                tags.append("[NEW]")
            if _first_use(url, date_iso, all_entries):
                tags.append("[FIRST]")
            tag_str = " ".join(tags) + (" " if tags else "")
            authors = ref.get("authors", "?")
            year = ref.get("year", "?")
            title = ref.get("title", "?")
            lines.append(f"  {tag_str}{authors} ({year}). {title}. {url}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries-dir", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()

    out = render_summary(args.entries_dir, start=args.start, end=args.end, as_of=args.as_of)
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
