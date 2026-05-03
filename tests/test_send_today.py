"""Tests for scripts.send_today (the daily mailman)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.send_today import (
    BufferStatus,
    build_buffer_alert_email,
    build_overdue_alert_email,
    count_future_entries,
    decide_dispatch,
    find_entry,
    render_email,
)


VALID_ENTRY_YAML = """\
"2026-05-15":
  status: GENERATED
  category: metabolic
  stub: "insulin sensitivity reduction after partial sleep restriction"
  subject: "[Cld] Sleep Nudge - 2026-05-15 - metabolic: insulin sensitivity reduction after partial sleep restriction"
  body: |
    Sample scientific paragraph.

    Plain language: get some sleep.

    References
    Author (2024). Title. Journal. https://example.com/paper

    ---
  generated_at: "2026-05-02T03:11:00Z"
  generator_model: "claude-opus-4-7"

"2026-05-16":
  status: GENERATION_FAILED
  category: cognitive
  stub: "memory consolidation in REM"
  failure_reason: "Could not verify any cited references after 2 attempts"
  generated_at: "2026-05-02T03:11:00Z"
"""


@pytest.fixture
def entries_dir(tmp_path: Path) -> Path:
    d = tmp_path / "entries"
    d.mkdir()
    (d / "2026-05.yaml").write_text(VALID_ENTRY_YAML)
    return d


def test_find_entry_returns_dict_for_existing_date(entries_dir: Path) -> None:
    entry = find_entry(entries_dir, "2026-05-15")
    assert entry is not None
    assert entry["status"] == "GENERATED"
    assert entry["category"] == "metabolic"


def test_find_entry_returns_none_for_missing_date(entries_dir: Path) -> None:
    assert find_entry(entries_dir, "2026-05-20") is None


def test_find_entry_returns_none_when_month_file_missing(entries_dir: Path) -> None:
    assert find_entry(entries_dir, "2026-09-01") is None


def test_count_future_entries_counts_today_and_after(entries_dir: Path) -> None:
    # entries fixture has 2026-05-15 (GENERATED) and 2026-05-16 (FAILED).
    # Only GENERATED days count toward the buffer; failed days are not usable.
    assert count_future_entries(entries_dir, "2026-05-15") == 1
    assert count_future_entries(entries_dir, "2026-05-16") == 0
    assert count_future_entries(entries_dir, "2026-05-17") == 0
    assert count_future_entries(entries_dir, "2026-05-14") == 1


def test_count_future_entries_aggregates_across_month_files(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    (d / "2026-05.yaml").write_text(
        '"2026-05-30": {status: GENERATED, category: x, stub: y, subject: s, body: b}\n'
    )
    (d / "2026-06.yaml").write_text(
        '"2026-06-01": {status: GENERATED, category: x, stub: y, subject: s, body: b}\n'
        '"2026-06-02": {status: GENERATED, category: x, stub: y, subject: s, body: b}\n'
    )
    assert count_future_entries(d, "2026-05-30") == 3
    assert count_future_entries(d, "2026-06-01") == 2
    assert count_future_entries(d, "2026-07-01") == 0


def test_count_future_entries_returns_zero_when_no_files(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    assert count_future_entries(d, "2026-05-15") == 0


def test_count_future_entries_excludes_failed_entries(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    (d / "2026-05.yaml").write_text(
        '"2026-05-30": {status: GENERATED, category: x, stub: y, subject: s, body: b}\n'
        '"2026-05-31": {status: GENERATION_FAILED, category: x, stub: y, failure_reason: r}\n'
    )
    # only the GENERATED one is a usable buffer day
    assert count_future_entries(d, "2026-05-30") == 1


def test_render_email_returns_subject_and_body_for_valid_entry(entries_dir: Path) -> None:
    entry = find_entry(entries_dir, "2026-05-15")
    rendered = render_email(entry, "2026-05-15")
    assert rendered.subject == entry["subject"]
    assert rendered.body == entry["body"]


def test_build_overdue_alert_has_loud_subject_and_reason(entries_dir: Path) -> None:
    rendered = build_overdue_alert_email("2026-05-20", reason="No entry found")
    assert "OVERDUE" in rendered.subject
    assert "2026-05-20" in rendered.subject
    assert "No entry found" in rendered.body


def test_build_overdue_alert_for_failed_entry(entries_dir: Path) -> None:
    entry = find_entry(entries_dir, "2026-05-16")
    rendered = build_overdue_alert_email(
        "2026-05-16", reason=f"Entry status=GENERATION_FAILED: {entry['failure_reason']}"
    )
    assert "OVERDUE" in rendered.subject
    assert "Could not verify" in rendered.body


def test_build_buffer_alert_has_warning_subject_and_count() -> None:
    status = BufferStatus(future_count=3, threshold=7, is_low=True)
    rendered = build_buffer_alert_email("2026-05-15", status)
    assert "BUFFER LOW" in rendered.subject
    assert "3" in rendered.body
    assert "7" in rendered.body


def test_decide_dispatch_happy_path_single_email_exit_zero(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    # 8 future-dated GENERATED entries -> buffer above threshold of 7
    body = ""
    for i in range(15, 23):
        body += (
            f'"2026-05-{i:02d}": {{status: GENERATED, category: x, stub: y, '
            f'subject: "S{i}", body: "B{i}"}}\n'
        )
    (d / "2026-05.yaml").write_text(body)
    plan = decide_dispatch(d, "2026-05-15", buffer_threshold=7)
    assert plan.exit_code == 0
    assert len(plan.emails) == 1
    assert plan.emails[0].subject == "S15"


def test_decide_dispatch_missing_entry_emits_overdue_alert_exit_nonzero(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    plan = decide_dispatch(d, "2026-05-15", buffer_threshold=7)
    assert plan.exit_code != 0
    assert len(plan.emails) == 1
    assert "OVERDUE" in plan.emails[0].subject


def test_decide_dispatch_failed_entry_emits_overdue_alert(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    (d / "2026-05.yaml").write_text(
        '"2026-05-15": {status: GENERATION_FAILED, category: x, stub: y, '
        'failure_reason: "verifier exhausted"}\n'
    )
    plan = decide_dispatch(d, "2026-05-15", buffer_threshold=7)
    assert plan.exit_code != 0
    assert "OVERDUE" in plan.emails[0].subject
    assert "verifier exhausted" in plan.emails[0].body


def test_decide_dispatch_low_buffer_appends_buffer_alert_email(tmp_path: Path) -> None:
    d = tmp_path / "entries"
    d.mkdir()
    # 3 future-dated GENERATED entries -> buffer below threshold of 7
    body = ""
    for i in range(15, 18):
        body += (
            f'"2026-05-{i:02d}": {{status: GENERATED, category: x, stub: y, '
            f'subject: "S{i}", body: "B{i}"}}\n'
        )
    (d / "2026-05.yaml").write_text(body)
    plan = decide_dispatch(d, "2026-05-15", buffer_threshold=7)
    assert plan.exit_code != 0
    assert len(plan.emails) == 2
    assert plan.emails[0].subject == "S15"
    assert "BUFFER LOW" in plan.emails[1].subject
