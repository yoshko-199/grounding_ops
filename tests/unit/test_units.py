"""`patterns.unit_at`: reading the unit a claim states after a numeral.

Interface v1.6. The matcher decides which unit a figure is in, and a wrong
reading contradicts a true claim or lets a figure in the wrong unit be
compared, so its edge cases are pinned here.
"""

from __future__ import annotations

import pytest

from engine.verification.patterns import unit_at

UNITS = {
    "percent": ("percent", "per cent", "%"),
    "percentage_points": ("percentage points",),
    "degrees_celsius": ("degrees celsius", "°c"),
    "degrees_fahrenheit": ("degrees fahrenheit", "°f"),
    # A whole-word prefix of the phrases above. Only longest-first matching
    # keeps "degrees Fahrenheit" from being read as this.
    "angular_degrees": ("degrees",),
}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("4.3 percent", ("percent", 11)),
        ("4.3%", ("percent", 4)),
        ("4.3 per cent of", ("percent", 12)),
        # The word boundary: the old hardcoded alternation read this as percent.
        ("0.3 percentage points", ("percentage_points", 21)),
        # Longest first: "degrees" alone is declared too, for another unit.
        ("212 degrees Fahrenheit", ("degrees_fahrenheit", 22)),
        ("90 degrees to the left", ("angular_degrees", 10)),
        ("100°C at sea level", ("degrees_celsius", 5)),
        ("212 Degrees Fahrenheit", ("degrees_fahrenheit", 22)),
    ],
)
def test_the_stated_unit_is_read(text: str, expected: tuple[str, int]) -> None:
    numeral_end = len(text.split()[0].rstrip("%°CcFf"))
    assert unit_at(text, numeral_end, UNITS) == expected


@pytest.mark.parametrize(
    "text",
    [
        "4.3 percentages of it",  # a phrase must end at a word boundary
        "4.3 points",             # not declared: no unit, not a guess
        "4.3",
        "4.3 of the percent",     # the phrase must follow the numeral directly
    ],
)
def test_no_unit_is_read_where_none_is_declared_right_there(text: str) -> None:
    assert unit_at(text, len("4.3"), UNITS) is None


def test_no_phrases_reads_no_unit() -> None:
    assert unit_at("212 degrees Fahrenheit", 3, {}) is None
