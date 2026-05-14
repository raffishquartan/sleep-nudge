"""Tests for scripts.render_summary_email."""

from __future__ import annotations

from pathlib import Path

from scripts.render_summary_email import render_summary


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_empty_range_includes_header_and_zero_counts(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    out = render_summary(d, start="2026-06-01", end="2026-06-30", as_of="2026-05-15")
    assert "Sleep Nudge generation summary" in out
    assert "Generated: 0" in out
    assert "Failed: 0" in out


def test_tldr_bullet_lists_each_date(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_yaml(
        d / "2026-06.yaml",
        """
"2026-06-01":
  status: GENERATED
  category: metabolic
  stub: "stub one"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/a"
      title: "Paper A"
      authors: "Auth A"
      year: 2024
      published_at: "2024-08"
"2026-06-02":
  status: GENERATED
  category: cognitive
  stub: "stub two"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/b"
      title: "Paper B"
      authors: "Auth B"
      year: 2025
      published_at: "2025-01"
""".strip(),
    )
    out = render_summary(d, start="2026-06-01", end="2026-06-30", as_of="2026-05-15")
    assert "2026-06-01 | metabolic | stub one" in out
    assert "2026-06-02 | cognitive | stub two" in out
    assert "Generated: 2" in out


def test_failed_entries_flagged(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_yaml(
        d / "2026-06.yaml",
        """
"2026-06-01":
  status: GENERATION_FAILED
  category: metabolic
  stub: "tried but failed"
  failure_reason: "verifier exhausted"
""".strip(),
    )
    out = render_summary(d, start="2026-06-01", end="2026-06-30", as_of="2026-05-15")
    assert "[FAILED]" in out
    assert "Failed: 1" in out
    assert "verifier exhausted" in out


def test_new_flag_for_recent_papers(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    write_yaml(
        d / "2026-06.yaml",
        """
"2026-06-01":
  status: GENERATED
  category: metabolic
  stub: "stub"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/recent"
      title: "Recent Paper"
      authors: "X"
      year: 2026
      published_at: "2026-04"
    - url: "https://example.com/old"
      title: "Old Paper"
      authors: "Y"
      year: 2020
      published_at: "2020-01"
""".strip(),
    )
    # as_of is 2026-05-15. published 2026-04 is within 90 days -> [NEW]. 2020-01 -> not.
    out = render_summary(d, start="2026-06-01", end="2026-06-30", as_of="2026-05-15")
    assert "[NEW]" in out
    assert "Recent Paper" in out
    assert out.count("[NEW]") == 1


def test_first_flag_for_first_use_of_a_url(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    # historical entry uses urlA back in February
    write_yaml(
        d / "2026-02.yaml",
        """
"2026-02-15":
  status: GENERATED
  category: x
  stub: "old stub"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/A"
      title: "Paper A"
      authors: "X"
      year: 2023
      published_at: "2023-01"
""".strip(),
    )
    # range entry on June 1 also uses urlA -> NOT first. uses urlB -> FIRST.
    write_yaml(
        d / "2026-06.yaml",
        """
"2026-06-01":
  status: GENERATED
  category: x
  stub: "stub"
  subject: "S"
  body: "B"
  references:
    - url: "https://example.com/A"
      title: "Paper A"
      authors: "X"
      year: 2023
      published_at: "2023-01"
    - url: "https://example.com/B"
      title: "Paper B"
      authors: "Y"
      year: 2024
      published_at: "2024-06"
""".strip(),
    )
    out = render_summary(d, start="2026-06-01", end="2026-06-30", as_of="2026-05-15")
    # Paper A line should NOT be flagged [FIRST]; Paper B line SHOULD be.
    paper_a_line = next(line for line in out.splitlines() if "example.com/A" in line)
    paper_b_line = next(line for line in out.splitlines() if "example.com/B" in line)
    assert "[FIRST]" not in paper_a_line
    assert "[FIRST]" in paper_b_line
