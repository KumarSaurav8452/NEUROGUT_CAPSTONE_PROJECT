"""Count validation against Table S1 (PRD FR-4 step 5 / FR-9)."""

from __future__ import annotations


def compare_counts(expected: int, obtained: int, tolerance: int = 2) -> str:
    """PASS = exact match, WARN = within +/- tolerance, FAIL = further off (reported, never forced)."""
    diff = abs(int(obtained) - int(expected))
    if diff == 0:
        return "PASS"
    return "WARN" if diff <= tolerance else "FAIL"
