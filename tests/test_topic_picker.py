"""Tests for scripts.topic_picker."""

from __future__ import annotations

import pytest

from scripts.topic_picker import pick_category, pick_stub


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
