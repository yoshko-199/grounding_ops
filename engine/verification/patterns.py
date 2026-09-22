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
from typing import Final

# A numeral, with an optional unit marker. Kept deliberately narrow: a bare
# integer inside a date is caught by the time patterns first.
NUMBER: Final = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|percent|percentage points?|points?)?",
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
