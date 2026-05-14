"""Tests for scripts.build_used_history."""

from __future__ import annotations

from pathlib import Path

from scripts.build_used_history import build_used_history


def write_entries(entries_dir: Path, month: str, body: str) -> None:
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / f"{month}.yaml").write_text(body)


def test_empty_entries_dir_returns_empty(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == set()
    assert used.urls == set()


def test_includes_stub_and_urls_within_window(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_entries(
        d,
        "2026-04",
        """
"2026-04-15":
  status: GENERATED
  category: metabolic
  stub: "stub A"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/a"
    - url: "https://example.com/b"
""".strip(),
    )
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == {"stub A"}
    assert used.urls == {"https://example.com/a", "https://example.com/b"}


def test_excludes_entries_outside_window(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_entries(
        d,
        "2026-01",
        """
"2026-01-01":
  status: GENERATED
  category: metabolic
  stub: "old stub"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/old"
""".strip(),
    )
    # 2026-05-15 minus 90 days = 2026-02-14, so 2026-01-01 is outside the window
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == set()
    assert used.urls == set()


def test_excludes_future_dated_entries(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_entries(
        d,
        "2026-06",
        """
"2026-06-01":
  status: GENERATED
  category: metabolic
  stub: "future stub"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/future"
""".strip(),
    )
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == set()
    assert used.urls == set()


def test_failed_entries_dedup_stubs_but_not_urls(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_entries(
        d,
        "2026-04",
        """
"2026-04-20":
  status: GENERATION_FAILED
  category: metabolic
  stub: "tried but failed"
  failure_reason: "verifier exhausted"
""".strip(),
    )
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == {"tried but failed"}
    assert used.urls == set()


def test_aggregates_across_monthly_files(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_entries(
        d,
        "2026-04",
        """
"2026-04-15":
  status: GENERATED
  category: metabolic
  stub: "stub from april"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/april"
""".strip(),
    )
    write_entries(
        d,
        "2026-05",
        """
"2026-05-10":
  status: GENERATED
  category: cognitive
  stub: "stub from may"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/may"
""".strip(),
    )
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == {"stub from april", "stub from may"}
    assert used.urls == {"https://example.com/april", "https://example.com/may"}


def test_handles_missing_references_field(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_entries(
        d,
        "2026-04",
        """
"2026-04-15":
  status: GENERATED
  category: metabolic
  stub: "no refs"
  subject: "S"
  body: "B"
""".strip(),
    )
    used = build_used_history(d, as_of="2026-05-15", window_days=90)
    assert used.stubs == {"no refs"}
    assert used.urls == set()
