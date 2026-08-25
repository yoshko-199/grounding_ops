"""Claim intake — scanning declared sources and accounts for candidate claims.

This package harvests *claims to check*.  It never harvests *evidence to check
them against*.  The distinction is the whole reason it may exist at all, and
every module here is written to keep it visible rather than merely true.

Adapted from the scraper in `auto-karpathy`__, which solves the same shape of
problem — one logical account, several unreliable transports, none of them
offering a real API — and solves it in a way that would break this system if
copied directly.  Four of its behaviours are inverted here, each against a
rule the engine already enforces:

1. **A failed scan returns a reason, never an empty list.**  ``scrape_tweets``
   returns ``[]`` whether every mirror timed out or the account genuinely has
   no posts.  §6.1 keeps *unreachable* and *reached, nothing there* apart and
   AC-14 asserts neither collapses into the other, so :class:`~plugins.harvest
   .outcome.Reach` has three states and ``REACHED`` with no items cannot be
   constructed.
2. **The cache expires.**  ``seen.json`` is a permanent set; §8 requires the
   opposite — a TTL from the source's cadence, expired entries re-pulled and
   never served.  There is no serve-stale-on-failure branch in
   :mod:`plugins.harvest.cache`, for the same reason AC-8 forbids one in the
   store.
3. **Every record says which backend produced it.**  ``Tweet`` does not, and
   the backends disagree: one returns HTML, another returns it stripped.
   Since §9.7.1 anchors derived elements to spans of the original, text that
   was silently rewritten in transit is a defect that surfaces much later, as
   a span that no longer resolves.  :class:`~plugins.harvest.records
   .CandidateClaim` keeps the raw body alongside the cleaned text and names
   every transform applied between them.
4. **There is no model-in-the-loop backend.**  ``_try_claude_agent`` asks a
   model with web search to return JSON that then becomes data.  That is
   precisely the path ``engine/custodians/base.py`` exists to exclude.  It is
   not reimplemented here in any form.

__ https://github.com/JuliusBrussee/auto-karpathy
"""

from plugins.harvest.outcome import FetchOutcome, Reach
from plugins.harvest.records import (
    CandidateClaim,
    DatePrecision,
    Provenance,
    TextTransform,
    UndatedClaim,
)
from plugins.harvest.scan import ScanResult, SourceReport
from plugins.harvest.sources import Backend, BackendKind, InvalidSource, Source

# ``scan`` — the function — is deliberately not re-exported. Binding it here
# would shadow the ``plugins.harvest.scan`` submodule on the package, so
# ``from plugins.harvest import scan`` would hand a caller the function where
# they asked for the module. Import it as ``from plugins.harvest.scan import
# scan`` when you want the function.

__all__ = [
    "Backend",
    "BackendKind",
    "CandidateClaim",
    "DatePrecision",
    "FetchOutcome",
    "InvalidSource",
    "Provenance",
    "Reach",
    "ScanResult",
    "Source",
    "SourceReport",
    "TextTransform",
    "UndatedClaim",
]
