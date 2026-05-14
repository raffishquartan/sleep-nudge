"""Tests for scripts.write_entry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.write_entry import EntryValidationError, write_entry


def base_generated() -> dict:
    return {
        "status": "GENERATED",
        "category": "metabolic",
        "stub": "stub A",
        "subject": "[Cld] Sleep Nudge - 2026-05-15 - metabolic: stub A",
        "body": "Body text",
    }


def test_write_new_entry_creates_month_file(tmp_path: Path) -> None:
    entries_dir = tmp_path / "entries"
    write_entry(entries_dir, "2026-05-15", base_generated())
    file_path = entries_dir / "2026-05.yaml"
    assert file_path.exists()
    data = yaml.safe_load(file_path.read_text())
    assert "2026-05-15" in data
    assert data["2026-05-15"]["status"] == "GENERATED"


def test_write_entry_preserves_other_dates_in_same_month(tmp_path: Path) -> None:
    entries_dir = tmp_path / "entries"
    write_entry(entries_dir, "2026-05-15", base_generated())
    second = base_generated()
    second["stub"] = "stub B"
    write_entry(entries_dir, "2026-05-16", second)

    data = yaml.safe_load((entries_dir / "2026-05.yaml").read_text())
    assert set(data.keys()) == {"2026-05-15", "2026-05-16"}
    assert data["2026-05-15"]["stub"] == "stub A"
    assert data["2026-05-16"]["stub"] == "stub B"


def test_write_entry_overwrites_same_date(tmp_path: Path) -> None:
    entries_dir = tmp_path / "entries"
    write_entry(entries_dir, "2026-05-15", base_generated())
    updated = base_generated()
    updated["stub"] = "replaced stub"
    write_entry(entries_dir, "2026-05-15", updated)

    data = yaml.safe_load((entries_dir / "2026-05.yaml").read_text())
    assert data["2026-05-15"]["stub"] == "replaced stub"


def test_invalid_status_rejected(tmp_path: Path) -> None:
    bad = base_generated()
    bad["status"] = "WEIRD"
    with pytest.raises(EntryValidationError, match="status"):
        write_entry(tmp_path / "entries", "2026-05-15", bad)


def test_malformed_date_rejected(tmp_path: Path) -> None:
    with pytest.raises(EntryValidationError, match="date"):
        write_entry(tmp_path / "entries", "2026-13-99", base_generated())


def test_generated_requires_body(tmp_path: Path) -> None:
    bad = base_generated()
    del bad["body"]
    with pytest.raises(EntryValidationError, match="body"):
        write_entry(tmp_path / "entries", "2026-05-15", bad)


def test_generated_requires_subject(tmp_path: Path) -> None:
    bad = base_generated()
    del bad["subject"]
    with pytest.raises(EntryValidationError, match="subject"):
        write_entry(tmp_path / "entries", "2026-05-15", bad)


def test_generated_requires_category_and_stub(tmp_path: Path) -> None:
    bad = base_generated()
    del bad["category"]
    with pytest.raises(EntryValidationError, match="category"):
        write_entry(tmp_path / "entries", "2026-05-15", bad)


def test_failed_entry_requires_failure_reason(tmp_path: Path) -> None:
    bad = {
        "status": "GENERATION_FAILED",
        "category": "metabolic",
        "stub": "stub X",
    }
    with pytest.raises(EntryValidationError, match="failure_reason"):
        write_entry(tmp_path / "entries", "2026-05-15", bad)


def test_failed_entry_accepted_with_failure_reason(tmp_path: Path) -> None:
    entries_dir = tmp_path / "entries"
    entry = {
        "status": "GENERATION_FAILED",
        "category": "metabolic",
        "stub": "stub X",
        "failure_reason": "verifier exhausted",
    }
    write_entry(entries_dir, "2026-05-15", entry)
    data = yaml.safe_load((entries_dir / "2026-05.yaml").read_text())
    assert data["2026-05-15"]["failure_reason"] == "verifier exhausted"
