"""Shared surface patterns for Stages 1 and 2.

These are language-general shapes — numerals, date forms, directional verbs.
Anything whose surface form is jurisdictional or language-specific lives in a
pack lexicon (interface §3.6), not here, because §9.4 puts all jurisdictional
knowledge in packs and none in the pipeline.

The English directional and predictive vocabularies below are the one place
that boundary is uncomfortable, and it is worth naming rather than hiding:
they are properties of a language, not of a jurisdiction, and the pack
interface has no language-vocabulary block outside the lexicon's derivation
triggers.  A second language would want them declared alongside those.  See
the note in ``decompose.py``.
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

RISE: Final = re.compile(
    r"\b(rose|rise|risen|rising|rises|increased|increases|increasing|grew|grown|grows|"
    r"climbed|climbs|doubled|tripled|surged|surges|up|higher)\b",
    re.I,
)

FALL: Final = re.compile(
    r"\b(fell|fall|fallen|falling|falls|decreased|decreases|decreasing|dropped|drops|"
    r"declined|declines|halved|shrank|shrunk|plunged|plunges|down|lower)\b",
    re.I,
)

PREDICTION: Final = re.compile(
    r"\b(will|shall|going\ to|expected\ to|forecast(?:ed)?\ to|next\ (?:year|month|quarter)|"
    r"by\ 20\d{2}|projected)\b",
    re.I | re.X,
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
