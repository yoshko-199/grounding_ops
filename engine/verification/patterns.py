"""Shared surface patterns for Stages 1 and 2.

These are language-general shapes — numerals, date forms. Anything whose
surface form is language-specific, not just jurisdiction-specific, lives in a
pack lexicon (interface §3.6) instead: directional (rise/fall) and predictive
vocabulary moved there in v1.4, as :class:`~engine.packs.schema.SurfaceCategory`,
because a pack that declared a language without a lexicon block for its own
direction words under-fired on every claim in that language, silently.

What is still here and still English-shaped: ``NUMBER`` and ``TIME_PERIOD``
recognise digit and date shapes, not words, and month names are the one
partly-lexical exception inside ``TIME_PERIOD`` — not moved in this pass, and
worth the same scrutiny this module's directional vocabulary just received.

:func:`matches_any` and :func:`finditer_any` are the lexicon-vocabulary
counterpart to the compiled patterns below: given the phrases a pack declares
for one :class:`~engine.packs.schema.SurfaceCategory`, they find them in
claim text with the same word-boundary exactness the old hardcoded regexes
had, so moving a category out of this module changed *where* the phrases live,
not *how* they are matched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from engine.packs.schema import Scale

if TYPE_CHECKING:
    from engine.packs.schema import Lexicon

# A numeral, with an optional unit marker. Kept deliberately narrow: a bare
# integer inside a date is caught by the time patterns first.
#
# Not a digit joined to a word by a hyphen. "Covid-19", "F-35" and "G-7" are
# names, and decomposing their digits made a quantity element the claim never
# asserted, listed in the ledger as unverified. A number after a space or a
# digit ("fell to -5", "2021-22") is still a number.
NUMBER: Final = re.compile(
    r"(?<![\w.])(?<![^\W\d_][-‐‑])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|percent|percentage points?|points?)?",
    re.I,
)

TIME_PERIOD: Final = re.compile(
    r"""(
        over\ the\ (?:last|past)\ (?:\w+)\ (?:years?|months?|quarters?|decades?)
      | (?:in|during|for)\ (?:the\ year\ )?\d{4}
      | since\ \d{4}
      | between\ \d{4}\ and\ \d{4}
      | (?:last|this|past)\ (?:year|month|quarter|decade)
      | \d{4}-\d{2}
      | (?:january|february|march|april|may|june|july|august|september|october|november|december)\ \d{4}
    )""",
    re.I | re.X,
)

# Years named inside a time period, used to check the retrieved series
# actually covers the period a claim scopes itself to.
YEAR: Final = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")

def matches_any(text: str, phrases: tuple[str, ...]) -> bool:
    """Whether any lexicon-declared phrase occurs in ``text``.

    Word-boundary exact and case-insensitive — the same exactness the old
    ``RISE``/``FALL``/``PREDICTION`` compiled patterns had, now applied to
    pack-declared phrases instead of a hardcoded English alternation.
    """
    return any(
        re.search(rf"\b{re.escape(phrase)}\b", text, re.I) for phrase in phrases
    )


def finditer_any(text: str, phrases: tuple[str, ...]) -> list[re.Match[str]]:
    """Every match of every lexicon-declared phrase, unordered.

    Callers that need span order sort the result — see
    ``decompose._resolve_overlaps``, which already sorts its candidates and
    would do so again regardless of the order matches arrive in here.
    """
    return [
        match
        for phrase in phrases
        for match in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.I)
    ]

def unit_at(
    text: str, position: int, unit_phrases: dict[str, tuple[str, ...]]
) -> tuple[str, int] | None:
    """The pack-declared unit named at ``position``, and where its phrase ends.

    Optional whitespace first, then the longest declared phrase that matches
    there, case-insensitively, and ends at a word boundary. Longest-first so
    that "degrees Fahrenheit" is not read as a bare "degrees" some other unit
    declares; the boundary so that "percent" is never read out of
    "percentage". The old hardcoded alternation had no boundary and tried
    "percent" first, so it read "percentage points" as percent.
    """
    start = position
    while start < len(text) and text[start] in " \t\u00a0":
        start += 1
    lowered = text.lower()
    candidates = sorted(
        ((phrase, unit) for unit, phrases in unit_phrases.items() for phrase in phrases),
        key=lambda pair: -len(pair[0]),
    )
    for phrase, unit in candidates:
        end = start + len(phrase)
        if lowered[start:end] != phrase.lower():
            continue
        if phrase[-1:].isalnum() and end < len(text) and (text[end].isalnum() or text[end] == "_"):
            continue
        return unit, end
    return None


def unit_before(
    text: str, position: int, unit_prefixes: dict[str, tuple[str, ...]]
) -> tuple[str, int] | None:
    """The pack-declared unit written just before ``position``, and where it starts.

    The mirror of :func:`unit_at`: optional whitespace back from the numeral,
    then the longest declared prefix that ends there, case-insensitively, and
    starts at a word boundary. Longest first, so "US$5" is read as the whole
    "US$" rather than a bare "$" some other unit declares; the boundary, so
    "USD" is never read out of the end of "XUSD".
    """
    end = position
    while end > 0 and text[end - 1] in " \t\u00a0":
        end -= 1
    lowered = text.lower()
    candidates = sorted(
        ((phrase, unit) for unit, phrases in unit_prefixes.items() for phrase in phrases),
        key=lambda pair: -len(pair[0]),
    )
    for phrase, unit in candidates:
        start = end - len(phrase)
        if start < 0 or lowered[start:end] != phrase.lower():
            continue
        if phrase[:1].isalnum() and start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            continue
        return unit, start
    return None


@dataclass(frozen=True, slots=True)
class QuantityReading:
    """What surrounds one numeral: [unit prefix] numeral [scale word] [unit].

    One reading, shared by decomposition (which anchors the element over all
    of it) and the element verdict (which compares it), so the two can never
    disagree about what a claim said.
    """

    start: int
    end: int
    exponent: int
    units: tuple[str, ...]


def read_quantity(text: str, match: re.Match[str], lexicon: Lexicon) -> QuantityReading:
    """Read a NUMBER match in ``text`` against the lexicon's declared forms.

    A unit written before the numeral (interface v1.7), then a scale word
    straight after it (v1.8), then a unit after that (v1.6): "£5bn",
    "5 billion pounds", "28.7 thousand people". Anything undeclared is left
    out, and NUMBER's own English unit group still ends a bare match.
    """
    prefix = unit_before(text, match.start(1), lexicon.unit_prefixes)
    scale = unit_at(
        text, match.end(1), {s.value: words for s, words in lexicon.scale_words.items()}
    )
    after = unit_at(text, scale[1] if scale else match.end(1), lexicon.unit_phrases)
    if after:
        end = after[1]
    elif scale:
        end = scale[1]
    else:
        end = match.end()
    return QuantityReading(
        start=prefix[1] if prefix else match.start(),
        end=end,
        exponent=Scale(scale[0]).exponent if scale else 0,
        units=tuple(found[0] for found in (prefix, after) if found),
    )


# Tokens carrying no measure identity, dropped before measure binding so that
# an incidental "the" does not count as evidence for a measure named "The
# Something Index".
STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
        "is", "are", "was", "were", "be", "been", "by", "as", "with", "from",
        "that", "this", "it", "its", "has", "have", "had", "not", "no",
        "over", "under", "per", "index", "rate", "national",
    }
)


def tokens(text: str) -> list[str]:
    """Lowercased word tokens, punctuation stripped."""
    return re.findall(r"[a-z0-9']+", text.lower())


def stem(token: str) -> str:
    """A deliberately crude stemmer.

    Enough to match "prices" against "price" and "seekers" against "seeker".
    Not enough to conflate distinct measures, which is the failure that would
    matter: §3's whole argument is that measure identity is the unit of
    correctness, so a stemmer that collapsed two measures into one would be
    worse than no stemmer at all.
    """
    for suffix in ("ies", "es", "s"):
        if len(token) > 3 and token.endswith(suffix):
            return token[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return token


def significant(text: str) -> set[str]:
    """Stemmed, stopword-free tokens."""
    return {stem(t) for t in tokens(text) if t not in STOPWORDS and len(t) > 2}
