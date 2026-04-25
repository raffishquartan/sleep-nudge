"""Shared pytest fixtures for sleep-nudge tests."""

from __future__ import annotations

import random

import pytest


@pytest.fixture
def seeded_rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def sample_bank() -> dict[str, list[str]]:
    return {
        "cardiovascular": ["A1", "A2", "A3"],
        "metabolic": ["B1", "B2"],
        "cognitive": ["C1", "C2", "C3", "C4"],
    }


@pytest.fixture
def sample_day_map() -> dict[str, list[str]]:
    return {
        "monday": ["cardiovascular", "metabolic"],
        "tuesday": ["cognitive"],
    }
