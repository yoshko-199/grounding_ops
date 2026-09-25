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


# -- written before the number (interface v1.7) ---------------------------------

from engine.verification.patterns import unit_before  # noqa: E402

PREFIXES = {
    "pounds_sterling": ("£", "GBP"),
    "us_dollars": ("$", "US$", "USD"),
    # "$" is a suffix of "US$" and of this; only longest-first keeps "A$5"
    # from being read as US dollars.
    "australian_dollars": ("A$",),
}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("£5", ("pounds_sterling", 0)),
        ("£ 5", ("pounds_sterling", 0)),
        ("costs GBP 5", ("pounds_sterling", 6)),
        ("costs US$5", ("us_dollars", 6)),
        ("costs $5", ("us_dollars", 6)),
        ("costs A$5", ("australian_dollars", 6)),
        ("costs usd 5", ("us_dollars", 6)),
    ],
)
def test_a_unit_written_before_the_number_is_read(text: str, expected: tuple[str, int]) -> None:
    numeral_start = next(i for i, c in enumerate(text) if c.isdigit())
    assert unit_before(text, numeral_start, PREFIXES) == expected


@pytest.mark.parametrize(
    "text",
    [
        "XUSD 5",       # a prefix must start at a word boundary
        "rose 5",       # not declared
        "£ and 5",      # it must end right before the number
        "5",
    ],
)
def test_no_prefix_is_read_where_none_is_declared_right_there(text: str) -> None:
    numeral_start = next(i for i, c in enumerate(text) if c.isdigit())
    assert unit_before(text, numeral_start, PREFIXES) is None


def test_no_prefixes_reads_no_prefix() -> None:
    assert unit_before("£5", 1, {}) is None


# -- scale words (interface v1.8) -------------------------------------------------

import pathlib  # noqa: E402

from engine.codes import JurisdictionCode, LanguageCode  # noqa: E402
from engine.packs.registry import PackRegistry  # noqa: E402
from engine.verification.patterns import NUMBER, read_quantity  # noqa: E402

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"


def _reading(text: str):
    lexicon = PackRegistry.from_directory(FIXTURE).get(JurisdictionCode("ZZ")).lexicon(
        LanguageCode("en")
    )
    return read_quantity(text, NUMBER.search(text), lexicon)


@pytest.mark.parametrize(
    "text,span,exponent,units",
    [
        ("£5bn", "£5bn", 9, ("pounds_sterling",)),
        ("28.7 thousand people", "28.7 thousand people", 3, ("persons",)),
        ("28.7k", "28.7k", 3, ()),
        ("US$ 1.2 trillion", "US$ 1.2 trillion", 12, ("us_dollars",)),
        ("5 million", "5 million", 6, ()),
        # A scale word must end at a word boundary.
        ("5 billionaires", "5 ", 0, ()),
        ("4.2 percent", "4.2 percent", 0, ("percent",)),
    ],
)
def test_the_scale_word_is_read_between_the_number_and_its_unit(
    text: str, span: str, exponent: int, units: tuple[str, ...]
) -> None:
    reading = _reading(text)
    assert text[reading.start:reading.end] == span
    assert reading.exponent == exponent
    assert reading.units == units


# -- approximation words (interface v1.9) --------------------------------------------


@pytest.mark.parametrize(
    "text,span,approximate",
    [
        ("about 29,000", "about 29,000", True),
        ("roughly £5bn", "roughly £5bn", True),
        ("around 28.7 thousand people", "around 28.7 thousand people", True),
        ("Approximately 30", "Approximately 30", True),
        # Bounds are not approximations, and a word must start at a boundary.
        ("nearly 29,000", "29,000", False),
        ("the roundabout 5", "5", False),
        ("29,000", "29,000", False),
    ],
)
def test_an_approximation_word_joins_the_figure(text: str, span: str, approximate: bool) -> None:
    reading = _reading(text)
    assert text[reading.start:reading.end].strip() == span
    assert reading.approximate is approximate
