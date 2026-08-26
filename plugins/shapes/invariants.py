"""Properties that must hold for every claim, whatever the verdict.

A fuzzer has no ground truth. It cannot ask whether *Misleading* was the right
call, and pretending otherwise would make it a second, worse implementation of
the thing it is testing. What it can ask is whether the artifact contradicts
itself, and that is enough: both defects found by hand in this repository
violate one of the checks below.

Each invariant names the failure it generalises. An invariant with no story
behind it tends to encode the implementation rather than a requirement, and
then fails on every correct change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from engine.elements import ElementKind, ElementStatus

_NUMERAL = re.compile(r"(?<![\w])\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class Violation:
    invariant: str
    claim: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - reporting aid
        return f"[{self.invariant}] {self.claim!r}\n    {self.detail}"


def _render_survives(claim: str, run, rendered: str | None) -> str | None:
    """The render must not raise.

    Generalises the crash on "corporate tax rose to 25 percent ... therefore
    ...": a figure the claimant stated reached output through the prose
    channel, and AC-7 refused it. Failing closed was right; crashing on a
    claim's own numbers was not. `rendered is None` means the caller caught an
    exception.
    """
    if rendered is None:
        return "render() raised"
    return None


def _verdict_present(claim: str, run, rendered: str | None) -> str | None:
    """§7.5 — every claim gets an answer, including Insufficient Data."""
    if run.artifact.verdict is None or run.artifact.verdict.label is None:
        return "artifact carries no verdict label"
    return None


def _period_never_contradicted(claim: str, run, rendered: str | None) -> str | None:
    """A period scopes a comparison; it is not a figure to compare.

    This is the defect that labelled "unemployment fell in 2021" Substantially
    Inaccurate — the year was compared against the unemployment rate. A
    contradicted period is always this bug, never a finding.
    """
    for element in run.elements:
        if (
            element.kind is ElementKind.TIME_PERIOD
            and element.status is ElementStatus.CONTRADICTED
        ):
            return (
                f"period {element.fragment!r} came back contradicted, which means it "
                "was compared as a figure"
            )
    return None


def _ledger_agrees_with_routing(claim: str, run, rendered: str | None) -> str | None:
    """The artifact must not contradict itself about its own process.

    Generalises the state a real pack made reachable: ROUTING named a bound
    measure while the discard ledger said no measure was bound. Nothing was
    over-claimed, but the artifact misreported why it had failed.
    """
    if not run.artifact.routing:
        return None
    for entry in run.artifact.ledger:
        if "no measure was bound" in entry.reason:
            return (
                f"routing names {run.artifact.routing[0].measure!r} while the ledger "
                f"says no measure was bound for {entry.fragment!r}"
            )
    return None


def _spans_resolve(claim: str, run, rendered: str | None) -> str | None:
    """§9.7.1 as extended to elements: every span resolves to its fragment."""
    for element in run.elements:
        resolved = claim[element.span.start : element.span.end]
        if resolved != element.fragment:
            return (
                f"element span {element.span.start}:{element.span.end} resolves to "
                f"{resolved!r}, not {element.fragment!r}"
            )
    return None


def _derived_spans_resolve(claim: str, run, rendered: str | None) -> str | None:
    """§9.7.1 — a derived element anchors to a span of the original."""
    for element in run.derived:
        resolved = claim[element.span.start : element.span.end]
        if not resolved.strip():
            return f"derived element anchors to an empty span for {element.text!r}"
    return None


def _derived_introduces_no_new_word(claim: str, run, rendered: str | None) -> str | None:
    """§9.7.3 — no entity the claim does not contain.

    Enforced upstream in derivation, and checked again here because the flank
    bounds changed once already and wider flanks are exactly how new content
    would arrive.
    """
    from plugins.shapes.run import SCAFFOLD_WORDS

    claim_words = {w.lower() for w in _WORD.findall(claim)}
    for element in run.derived:
        for word in _WORD.findall(element.text):
            lowered = word.lower()
            if lowered in claim_words or lowered in SCAFFOLD_WORDS:
                continue
            return (
                f"derived text introduces {word!r}, which is in neither the claim nor "
                "a scaffold"
            )
    return None


def _derived_texts_are_distinct(claim: str, run, rendered: str | None) -> str | None:
    """Two operations producing identical text means the flanks collapsed.

    Generalises the two-trigger flank defect: when bounds are wrong, adjacent
    triggers converge on the same span and emit the same proposition under
    different operation labels.
    """
    seen: dict[str, str] = {}
    for element in run.derived:
        key = element.text.strip().lower()
        if key in seen:
            return (
                f"{seen[key]} and {element.operation.value} produced identical text: "
                f"{element.text!r}"
            )
        seen[key] = element.operation.value
    return None


def _discarded_content_stays_out(claim: str, run, rendered: str | None) -> str | None:
    """§7.1 — what was removed does not reappear in the reconstruction.

    An out-of-scope fragment surfacing in the rebuilt claim would put causal or
    evaluative language back into the one sentence presented as grounded.
    """
    if not run.artifact.does_reconstruct or rendered is None:
        return None
    reconstruction = _reconstruction_of(rendered)
    if reconstruction is None:
        return None
    for element in run.elements:
        if element.status is not ElementStatus.OUT_OF_SCOPE:
            continue
        fragment = element.fragment.strip().lower()
        if len(fragment) > 3 and fragment in reconstruction.lower():
            return (
                f"out-of-scope fragment {element.fragment!r} appears in the "
                "reconstruction"
            )
    return None


def _reconstruction_of(rendered: str) -> str | None:
    lines = rendered.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "RECONSTRUCTED":
            return lines[index + 1] if index + 1 < len(lines) else None
    return None


Invariant = Callable[[str, object, "str | None"], "str | None"]

INVARIANTS: tuple[tuple[str, Invariant], ...] = (
    ("render-survives", _render_survives),
    ("verdict-present", _verdict_present),
    ("period-never-contradicted", _period_never_contradicted),
    ("ledger-agrees-with-routing", _ledger_agrees_with_routing),
    ("spans-resolve", _spans_resolve),
    ("derived-spans-resolve", _derived_spans_resolve),
    ("derived-introduces-no-new-word", _derived_introduces_no_new_word),
    ("derived-texts-are-distinct", _derived_texts_are_distinct),
    ("discarded-content-stays-out", _discarded_content_stays_out),
)
