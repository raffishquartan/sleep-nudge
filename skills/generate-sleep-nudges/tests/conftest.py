"""Shared fixtures for generate-sleep-nudges skill tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the skill's scripts/ importable as `scripts.X` when running pytest from the skill root.
SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))
