"""Topic-picker module for sleep-nudge daily emails."""

from __future__ import annotations

import random


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
