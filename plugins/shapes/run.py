"""Driving the engine over generated shapes, and reporting what broke.

Determinism is checked here rather than as an invariant, because it is the one
property that needs two runs of the same claim rather than one artifact. §9.9
requires reconstruction to be a pure function of the verified element set, so
the same claim must produce the same element-set hash and the same text every
time — anything else means retrieval timing, insertion order, or hash
iteration has leaked into the output.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore
from engine.verification.derive import SCAFFOLD, IMPLICATION_PREFIX
from plugins.shapes.invariants import INVARIANTS, Violation
from plugins.shapes.shapes import Shape, sample, shrink

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE_PACKS = ROOT / "packs" / "fixture"

#: Words a derived element may contain that the claim does not — the closed
#: scaffold set, plus the implication prefix the renderer adds.
SCAFFOLD_WORDS: frozenset[str] = frozenset(
    word.lower()
    for phrase in (*SCAFFOLD.values(), IMPLICATION_PREFIX)
    for word in phrase.replace(".", " ").split()
)


@dataclass
class FuzzReport:
    seed: int
    checked: int = 0
    violations: list[Violation] = field(default_factory=list)
    crashed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.violations and not self.crashed

    def summary(self) -> str:
        if self.clean:
            return f"{self.checked} shapes checked, no violations (seed {self.seed})"
        return (
            f"{self.checked} shapes checked, {len(self.violations)} violation(s), "
            f"{len(self.crashed)} crash(es) (seed {self.seed})"
        )


def _context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )


def _run_once(claim: str, registry, adapters, store):
    """Verify a claim, returning the run and its rendered form.

    A render that raises is reported rather than propagated: a crash is a
    finding, and a fuzzer that dies on its first one checks nothing else.
    """
    run = verify(claim, _context(), registry, adapters, store)
    try:
        rendered = run.artifact.render()
    except Exception:  # noqa: BLE001 - the exception is the finding
        rendered = None
    return run, rendered


def check(claim: str, registry, adapters, store) -> list[Violation]:
    """Every invariant against one claim, plus determinism."""
    found: list[Violation] = []
    run, rendered = _run_once(claim, registry, adapters, store)

    for name, invariant in INVARIANTS:
        try:
            detail = invariant(claim, run, rendered)
        except Exception as exc:  # noqa: BLE001 - a broken check is a finding
            detail = f"invariant raised {type(exc).__name__}: {exc}"
        if detail:
            found.append(Violation(name, claim, detail))

    # Determinism is checked on the rendered artifact, not on
    # `element_set_hash`. The hash covers element *ids*, which are fresh per
    # run, so two runs of one claim hash differently by construction — and
    # that is correct: §8 wants "two revisions with the same hash must have
    # identical text", which is a property of a *recorded* element set being
    # re-derived, not of the same claim being re-verified.
    #
    # This check originally asserted the hash was stable and reported every
    # claim as a violation. Worth recording rather than quietly deleting: an
    # invariant that encodes what the implementation seemed to do, instead of
    # what the spec requires, fails on correct behaviour and buries the real
    # findings underneath itself. It did exactly that on the first run.
    _, rendered_again = _run_once(claim, registry, adapters, store)
    if rendered != rendered_again:
        found.append(
            Violation(
                "determinism",
                claim,
                "the same claim rendered differently on a second run",
            )
        )

    return found


def fuzz(count: int = 400, seed: int = 0, packs: pathlib.Path | None = None) -> FuzzReport:
    """Check a deterministic sample of shapes, shrinking anything that fails."""
    registry = PackRegistry.from_directory(packs or FIXTURE_PACKS)
    adapters = build_fixture_custodians()
    store = RetrievalStore()
    report = FuzzReport(seed=seed)

    try:
        for shape in sample(count, seed):
            claim = shape.text.strip()
            if not claim:
                continue
            report.checked += 1
            try:
                violations = check(claim, registry, adapters, store)
            except Exception as exc:  # noqa: BLE001 - pipeline crash is a finding
                report.crashed.append((claim, f"{type(exc).__name__}: {exc}"))
                continue
            if violations:
                report.violations.extend(
                    _shrunk(shape, violations, registry, adapters, store)
                )
    finally:
        store.close()

    return report


def _shrunk(
    shape: Shape, violations: list[Violation], registry, adapters, store
) -> list[Violation]:
    """Re-report each violation against the smallest claim that still shows it."""
    out: list[Violation] = []
    for violation in violations:
        def still_fails(candidate: Shape, name: str = violation.invariant) -> bool:
            text = candidate.text.strip()
            if not text:
                return False
            try:
                return any(v.invariant == name for v in check(text, registry, adapters, store))
            except Exception:  # noqa: BLE001
                return False

        smallest = shrink(shape, still_fails)
        out.append(
            Violation(violation.invariant, smallest.text.strip(), violation.detail)
        )
    return out
