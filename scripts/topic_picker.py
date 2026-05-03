"""Topic-picker module for sleep-nudge daily emails."""

from __future__ import annotations

import json
import random
from pathlib import Path

import yaml


def seeded_rng_for_date(date_iso: str, *, salt: str = "") -> random.Random:
    """Return a deterministic RNG seeded by an ISO date string and an optional salt.

    Same (date_iso, salt) pair always produces the same sequence; different pairs
    produce uncorrelated sequences. Used by the generator skill so that re-running
    generation for a single date picks the same category/stub given the same
    prior-used-stubs context.
    """
    return random.Random(f"{date_iso}|{salt}")


def pick_category(day: str, day_map: dict[str, list[str]], rng: random.Random) -> str:
    return rng.choice(day_map[day])


def pick_stub(
    category: str,
    bank: dict[str, list[str]],
    state: list[str],
    rng: random.Random,
) -> str:
    all_stubs = bank[category]
    available = [s for s in all_stubs if s not in state]
    if not available:
        available = all_stubs
    return rng.choice(available)


def update_state(state: list[str], new_stub: str, max_window: int = 30) -> list[str]:
    return ([*state, new_stub])[-max_window:]


def build_subject(today: str, category: str, stub: str) -> str:
    return f"[Cld] Sleep Nudge - {today} - {category}: {stub}"


def load_day_categories(path: Path) -> dict[str, list[str]]:
    return yaml.safe_load(path.read_text())


def load_topic_bank(path: Path) -> dict[str, list[str]]:
    return yaml.safe_load(path.read_text())


def load_state(path: Path) -> list[str]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_state(path: Path, state: list[str]) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n")


def validate_bank(day_map: dict[str, list[str]], bank: dict[str, list[str]]) -> None:
    referenced = {c for cats in day_map.values() for c in cats}
    missing = referenced - set(bank.keys())
    if missing:
        raise ValueError(
            f"Categories referenced in day-map but missing from bank: {sorted(missing)}"
        )
