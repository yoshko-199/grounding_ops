"""Stage 8 — the claim-level verdict.

Spec §6.2 fixes the labels; §9.1 makes every verdict a *proposal* requiring
human confirmation; §9.3 and §9.5 impose two hard caps that apply regardless
of how the elements came out.

The caps are the part most worth getting right.  §9.3 on the unrunnable
sweep: "The third row is the one that keeps the sweep honest. Without it, an
unrunnable sweep would read as a clean pass, and the weakest-evidence claims
would receive the strongest label."  Silence is not endorsement, and the code
has to say so explicitly because nothing else will.
"""

from __future__ import annotations

from engine.elements import ContinuityStatus, Element, ElementStatus
from engine.verdicts import ProposedVerdict, Verdict
from engine.verification.sweep import SweepResult

__all__ = ["ProposedVerdict", "Verdict", "evaluate"]


def evaluate(
    elements: tuple[Element, ...],
    sweep: SweepResult,
    *,
    routed: bool,
    reconstructs: bool,
) -> ProposedVerdict:
    """Propose a claim-level verdict for the reconstructed claim."""
    if not routed:
        # Interface §4.1. Not an error state — §7.5 requires Insufficient
        # Data to render as a first-class answer, never styled as failure.
        return ProposedVerdict(
            Verdict.INSUFFICIENT_DATA,
            "No custodian of record settles this claim. This is an answer, not a "
            "failure to produce one.",
        )

    in_scope = [e for e in elements if not e.is_out_of_scope]
    verified = [e for e in in_scope if e.status is ElementStatus.VERIFIED]
    contradicted = [e for e in in_scope if e.status is ElementStatus.CONTRADICTED]
    contested = [e for e in in_scope if e.status is ElementStatus.CONTESTED_BY_DEFINITION]
    unreachable = [e for e in in_scope if e.status is ElementStatus.UNREACHABLE]

    if not in_scope:
        return ProposedVerdict(
            Verdict.INSUFFICIENT_DATA,
            "The claim decomposed into no element with an authoritative custodian.",
        )

    if unreachable and not verified and not contradicted:
        return ProposedVerdict(
            Verdict.INSUFFICIENT_DATA,
            "The custodians could not be reached this session. No figure was "
            "retrieved, and no cached figure was served in their place.",
        )

    # §9.5's cap. An element spanning an unlinked break cannot be Verified, so
    # the claim cannot be Accurate on that element.
    spliced = [
        e for e in in_scope if e.continuity_status is ContinuityStatus.UNLINKED_BREAK
    ]

    if contradicted and not verified:
        return ProposedVerdict(
            Verdict.FALSE,
            _tally("The claim is not supported by the record.", verified, contradicted,
                   contested, unreachable),
        )

    if contradicted:
        return ProposedVerdict(
            Verdict.SUBSTANTIALLY_INACCURATE,
            _tally("Significant parts of the claim conflict with the record.",
                   verified, contradicted, contested, unreachable),
        )

    if contested or spliced:
        return ProposedVerdict(
            Verdict.INDETERMINATE,
            _tally(
                "Custodians measure different things here, or the comparison spans a "
                "series break no linked series covers. Both figures are reported and "
                "the judgment is left to the reader.",
                verified, contradicted, contested, unreachable,
            ),
        )

    if not reconstructs:
        return ProposedVerdict(
            Verdict.INDETERMINATE,
            "The surviving elements do not compose into a coherent statement. They "
            "are listed rather than smoothed into a sentence.",
        )

    # §9.3's cap. This branch is the one that keeps the sweep honest.
    if not sweep.ran:
        return ProposedVerdict(
            Verdict.INDETERMINATE,
            "Every element verifies, but the robustness sweep could not run, so the "
            "claim has not been tested for baseline or window selection.",
            capped=True,
            cap_reason=sweep.reason_not_run,
        )

    if sweep.conclusion_flips:
        # The flipped alternatives are deliberately not named here. §9.3 makes
        # the flip table itself the evidence, and it renders with every row
        # citing the retrieval it was computed from; restating the alternatives
        # in prose would duplicate that while putting their identifiers —
        # window names like "3m" — into text no retrieval id travels with.
        return ProposedVerdict(
            Verdict.MISLEADING,
            "The elements verify, but the claim's conclusion does not hold under every "
            "admissible alternative the pack declares. The flip table below records "
            "which alternatives it fails under, and is the evidence for this label.",
        )

    return ProposedVerdict(
        Verdict.ACCURATE,
        _tally(
            "Every in-scope element verifies against its custodian, and the conclusion "
            "holds under every admissible baseline and window the pack declares.",
            verified, contradicted, contested, unreachable,
        ),
    )


def _tally(lead: str, verified, contradicted, contested, unreachable) -> str:
    """Summarise the element outcomes without emitting a bare numeral.

    Counts are deliberately not rendered. AC-7 requires every numeric literal
    in output to resolve to a retrieval id, and an element count resolves to
    none — it is a fact about the artifact rather than about the record. The
    information is not lost: the discard ledger lists every element that did
    not survive, and the citation record lists every retrieval.
    """
    present = [
        name
        for name, group in (
            ("verified", verified),
            ("contradicted", contradicted),
            ("contested by definition", contested),
            ("unreachable", unreachable),
        )
        if group
    ]
    if not present:
        return lead
    return f"{lead} Element outcomes present: {'; '.join(present)}."
