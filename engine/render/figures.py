"""Payload assembly with AC-7 enforced at the boundary.

Spec §3: every figure in any output originates from a recorded retrieval.
AC-7: "For every numeric literal in every output — figures, dates, amounts,
rankings, percentages, flip-table cells — assert it resolves to a
``retrievals.id`` [...] **This must fail the render, not warn.**"

The mechanism is a payload built from segments, each marked sourced or not.
Sourced segments come from a :class:`~engine.figures.Figure` or a retrieval's
reference period and carry a retrieval id.  Everything else is prose, and
prose may not contain a numeral.  The scan runs at render time and raises.

Warning instead of raising was never an option, and it is worth being clear
why: an unsourced figure that renders with a warning still renders, and the
artifact still carries custodian names and a citation trail around it.  The
warning goes to a log nobody reads and the number goes to a reader who
assumes it was checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from engine.figures import Figure
from engine.ids import RetrievalId

# Any numeral. Deliberately broad: AC-7 covers "figures, dates, amounts,
# rankings, percentages", so a bare year in prose is caught too.
_NUMERAL = re.compile(r"(?<![\w])\d[\d,]*(?:\.\d+)?")


class UnsourcedFigure(Exception):
    """Raised when a numeral reaches output without a retrieval behind it."""


# Marks a segment quoted verbatim from the claim under examination. Not a
# retrieval id, and deliberately not one: it must never appear in the citation
# trail, because nothing was retrieved.
_QUOTED = RetrievalId("quoted-from-claim")

# Marks a derived element's text: verbatim spans of the claim joined by a
# closed scaffold phrase (§9.7). Distinct from _QUOTED because the value is
# not one contiguous span of the claim and so cannot be checked as one — see
# :meth:`Payload.derived` for what is checked instead. Like _QUOTED, never a
# retrieval id and never in the citation trail.
_DERIVED = RetrievalId("derived-from-claim")


@dataclass(frozen=True, slots=True)
class _Segment:
    text: str
    retrieval_id: RetrievalId | None = None

    @property
    def sourced(self) -> bool:
        return self.retrieval_id is not None


class NotQuotedFromClaim(Exception):
    """Raised when text claimed to be quoted is not in the claim."""


@dataclass(slots=True)
class Payload:
    """An output payload that cannot carry an unsourced number."""

    claim_text: str = ""
    _segments: list[_Segment] = field(default_factory=list)

    def text(self, value: str) -> Payload:
        """Add prose. Prose may not contain a numeral."""
        self._segments.append(_Segment(value))
        return self

    def quoted(self, value: str) -> Payload:
        """Add text reproduced verbatim from the claim under examination.

        This is the one channel through which a numeral reaches output without
        a retrieval behind it, and it is narrow on purpose.

        The distinction it rests on is real: the claim is the *subject* of the
        artifact, not a finding of it. An artifact that could not show the
        claim it examined — including any figure the claim stated — would be
        unreadable, and quoting a claimant's own number asserts nothing about
        the record. Every figure the system itself *asserts* still requires a
        retrieval, and §3 is untouched.

        The narrowness is enforced rather than promised: a value that is not
        literally a span of the claim is rejected, so this cannot become a
        general-purpose route for unsourced numbers.
        """
        if value.strip() and value.strip() not in self.claim_text:
            raise NotQuotedFromClaim(
                f"{value.strip()[:60]!r} was passed as quoted from the claim but does "
                "not occur in it. Only verbatim spans of the claim under examination "
                "may bypass the retrieval requirement"
            )
        self._segments.append(_Segment(value, retrieval_id=_QUOTED))
        return self

    def derived(self, value: str) -> Payload:
        """Add a derived element's rendered text.

        A derived element is assembled from verbatim spans of the claim joined
        by a closed scaffold phrase (§9.7), so any numeral it carries is the
        claimant's own — the same position :meth:`quoted` occupies, reached by
        a different construction.  It cannot go through :meth:`quoted` because
        the scaffold makes the value a *composition* of claim spans rather
        than one contiguous span, and the substring check would reject it.

        So a different invariant is checked, and it is the one §3 actually
        cares about: **no numeral appears that the claim did not contain.**
        §9.7.3 already guarantees this upstream by rejecting any token absent
        from the claim; checking again here keeps AC-7 enforced at the
        boundary where output happens rather than resting on a guarantee made
        three modules away.

        Found by running a real claim carrying a figure through a real
        connective — "corporate tax ... 25 percent ... therefore ...".  Before
        this channel existed the render *crashed* on that shape, which is a
        large fraction of the political claims anyone would actually check.
        Failing closed was the right default; failing on the claimant's own
        numbers was still a defect.
        """
        claim_numerals = set(_NUMERAL.findall(self.claim_text))
        intruders = [n for n in _NUMERAL.findall(value) if n not in claim_numerals]
        if intruders:
            raise UnsourcedFigure(
                f"a derived element carries {sorted(set(intruders))}, which the claim "
                "does not contain. Derived elements are extracted from the claim's own "
                "text (§9.7.3); a numeral appearing here that the claimant did not "
                "write is an invented figure inside an authoritative-looking artifact"
            )
        self._segments.append(_Segment(value, retrieval_id=_DERIVED))
        return self

    def figure(self, value: Figure) -> Payload:
        """Add a figure, with its retrieval and reference period.

        §5 requires the reference period to render alongside the figure, and
        AC-7 asserts it, so the two are emitted together rather than left to
        the caller to remember.
        """
        self._segments.append(
            _Segment(f"{value.render()} ({value.reference_period})", value.retrieval_id)
        )
        return self

    def sourced(self, value: str, retrieval_id: RetrievalId) -> Payload:
        """Add text that carries numerals justified by a named retrieval."""
        self._segments.append(_Segment(value, retrieval_id))
        return self

    def line(self, value: str = "") -> Payload:
        return self.text(value + "\n")

    def render(self) -> str:
        """Assemble and scan. Raises rather than warns."""
        offenders: list[str] = []
        for segment in self._segments:
            if segment.sourced:
                continue
            offenders.extend(_NUMERAL.findall(segment.text))
        if offenders:
            raise UnsourcedFigure(
                f"output contains {len(offenders)} numeric literal(s) with no retrieval "
                f"behind them: {sorted(set(offenders))[:5]}. Every figure in any output "
                "must originate from a recorded retrieval against a named custodian (§3)"
            )
        return "".join(segment.text for segment in self._segments)

    def retrieval_ids(self) -> tuple[str, ...]:
        return tuple(
            str(s.retrieval_id)
            for s in self._segments
            if s.retrieval_id is not None
            and s.retrieval_id is not _QUOTED
            and s.retrieval_id is not _DERIVED
        )


def scan_prose(value: str) -> list[str]:
    """Numerals in a free-text string, for checking human-entered text.

    Used on ``amendment_rationale`` (AC-10): "Assert that
    ``amendment_rationale`` introducing a figure fails AC-7 exactly as
    pipeline output would."  §3 binds the reviewer exactly as it binds the
    pipeline.
    """
    return _NUMERAL.findall(value)
