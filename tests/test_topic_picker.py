"""Tests for scripts.topic_picker."""

from __future__ import annotations

import json

import pytest

from scripts.topic_picker import (
    build_subject,
    load_day_categories,
    load_state,
    load_topic_bank,
    pick_category,
    pick_stub,
    save_state,
    seeded_rng_for_date,
    update_state,
    validate_bank,
)


def test_seeded_rng_for_date_is_deterministic():
    rng_a = seeded_rng_for_date("2026-05-15")
    rng_b = seeded_rng_for_date("2026-05-15")
    assert [rng_a.random() for _ in range(5)] == [rng_b.random() for _ in range(5)]


def test_seeded_rng_for_date_differs_by_date():
    rng_a = seeded_rng_for_date("2026-05-15")
    rng_b = seeded_rng_for_date("2026-05-16")
    assert [rng_a.random() for _ in range(5)] != [rng_b.random() for _ in range(5)]


def test_seeded_rng_for_date_differs_by_salt():
    rng_cat = seeded_rng_for_date("2026-05-15", salt="category")
    rng_stub = seeded_rng_for_date("2026-05-15", salt="stub")
    assert [rng_cat.random() for _ in range(5)] != [rng_stub.random() for _ in range(5)]


def test_pick_category_with_seeded_rng_is_stable_for_same_date(sample_day_map):
    rng_first = seeded_rng_for_date("2026-05-15", salt="category")
    rng_second = seeded_rng_for_date("2026-05-15", salt="category")
    cat_first = pick_category("monday", sample_day_map, rng_first)
    cat_second = pick_category("monday", sample_day_map, rng_second)
    assert cat_first == cat_second


def test_pick_category_returns_one_of_the_day_candidates(sample_day_map, seeded_rng):
    result = pick_category("monday", sample_day_map, seeded_rng)
    assert result in sample_day_map["monday"]


def test_pick_category_raises_on_unknown_day(sample_day_map, seeded_rng):
    with pytest.raises(KeyError):
        pick_category("funday", sample_day_map, seeded_rng)


def test_pick_stub_returns_a_stub_in_the_category(sample_bank, seeded_rng):
    result = pick_stub("cognitive", sample_bank, state=[], rng=seeded_rng)
    assert result in sample_bank["cognitive"]


def test_pick_stub_excludes_state(sample_bank, seeded_rng):
    state = ["C1", "C2", "C3"]
    result = pick_stub("cognitive", sample_bank, state=state, rng=seeded_rng)
    assert result == "C4"


def test_pick_stub_falls_back_to_full_bank_when_all_excluded(sample_bank, seeded_rng):
    state = ["C1", "C2", "C3", "C4"]
    result = pick_stub("cognitive", sample_bank, state=state, rng=seeded_rng)
    assert result in sample_bank["cognitive"]


def test_update_state_appends():
    assert update_state(["a", "b"], "c") == ["a", "b", "c"]


def test_update_state_trims_to_max_window():
    state = [f"s{i}" for i in range(30)]
    new = update_state(state, "s30")
    assert len(new) == 30
    assert new[0] == "s1"
    assert new[-1] == "s30"


def test_update_state_custom_window():
    assert update_state(["a", "b", "c"], "d", max_window=2) == ["c", "d"]


def test_build_subject_format():
    s = build_subject(
        "2026-04-25",
        "cardiovascular",
        "Heart rate variability and parasympathetic recovery",
    )
    assert s == (
        "[Cld] Sleep Nudge - 2026-04-25 - cardiovascular: "
        "Heart rate variability and parasympathetic recovery"
    )


def test_load_day_categories_reads_yaml(tmp_path):
    p = tmp_path / "day-categories.yaml"
    p.write_text("monday: [a, b]\ntuesday: [c]\n")
    assert load_day_categories(p) == {"monday": ["a", "b"], "tuesday": ["c"]}


def test_load_topic_bank_reads_yaml(tmp_path):
    p = tmp_path / "topic-bank.yaml"
    p.write_text("a:\n  - stub1\n  - stub2\n")
    assert load_topic_bank(p) == {"a": ["stub1", "stub2"]}


def test_load_state_returns_empty_list_when_missing(tmp_path):
    assert load_state(tmp_path / "missing.json") == []


def test_load_state_reads_existing_json(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps(["x", "y"]))
    assert load_state(p) == ["x", "y"]


def test_save_state_round_trip(tmp_path):
    p = tmp_path / "state.json"
    save_state(p, ["a", "b"])
    assert json.loads(p.read_text()) == ["a", "b"]


def test_validate_bank_passes_when_all_categories_present():
    day_map = {"monday": ["a", "b"]}
    bank = {"a": ["s1"], "b": ["s2"]}
    validate_bank(day_map, bank)


def test_validate_bank_raises_on_missing_category():
    day_map = {"monday": ["a", "missing"]}
    bank = {"a": ["s1"]}
    with pytest.raises(ValueError, match="missing"):
        validate_bank(day_map, bank)
