"""AC-6 — Claimant blindness.

Constraint: spec §7.6.  No claimant metadata reaches the verification path.

The criterion calls itself the sharpest in the set, and the reason is worth
restating: "we are non-partisan" is an unfalsifiable claim about intent, and
this replaces it with something that either passes or does not.

Two halves.  The static half lives here from the first commit, because AC-6's
note is explicit that "reachability is tested alongside behaviour because an
unused pathway is a latent failure, not a passing one".  The differential
half — N runs under varying attributions, byte-identical output — arrives
with the pipeline it compares.
"""

from __future__ import annotations

import dataclasses
import typing
from datetime import date

import pytest

from engine.codes import InvalidCode, JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from tests.conformance._graph import modules_under, reachable

IDENTITY_MODULE = "engine.ingest.identity"
SPLIT_MODULE = "engine.ingest.split"


@pytest.mark.parametrize("module", modules_under("engine.verification"))
def test_identity_is_unreachable_from_verification(module: str) -> None:
    """No Stage 1-9 module can import its way to claimant identity."""
    reached = reachable(module)
    assert IDENTITY_MODULE not in reached, (
        f"{module} can reach {IDENTITY_MODULE}. Claimant metadata is reachable "
        "from the verification path, which fails AC-6 whether or not the path "
        "is currently taken."
    )
    assert SPLIT_MODULE not in reached, (
        f"{module} can reach {SPLIT_MODULE}, which holds both halves of the "
        "ingest split. Reaching it defeats the split (spec §9.8.1)."
    )


def test_the_reachability_harness_can_actually_detect_reachability() -> None:
    """Negative test of the harness itself.

    An import-graph assertion that never finds anything passes for both
    reasons — correct isolation, and a broken analyser — and those look
    identical in a green run.  ``engine.ingest.split`` is the one module that
    legitimately reaches identity, so it is the control: if the harness
    cannot see that edge, it cannot be trusted to see a violating one.
    """
    reached = reachable(SPLIT_MODULE)
    assert IDENTITY_MODULE in reached, (
        "the import-graph analyser failed to find a known direct import; "
        "every other assertion in this file is therefore meaningless"
    )
    # And transitively, through a module that imports the split.
    assert "engine.codes" in reached
    assert "engine.context" in reached


def test_verification_package_is_actually_populated() -> None:
    """Guard against the parametrised test above silently covering nothing.

    ``modules_under`` returning an empty or near-empty list would make the
    reachability test vacuous.  Once stages land, this asserts they are in
    scope rather than sitting outside the package the criterion guards.
    """
    modules = modules_under("engine.verification")
    assert "engine.verification" in modules


def test_claim_context_carries_no_free_text() -> None:
    """AC-17's structural test, asserted on the type itself.

    Every field crossing into verification is a code or a date.  A free-text
    field is a channel regardless of what anyone intends to put in it.
    """
    hints = typing.get_type_hints(ClaimContext)
    for name, hint in hints.items():
        assert str not in _union_members(hint), (
            f"ClaimContext.{name} admits str. Spec §9.8.1 requires every field "
            "crossing into the verification path to be a code or a date."
        )


def _union_members(hint: object) -> set[object]:
    origin = typing.get_origin(hint)
    if origin is typing.Union or origin is type(int | str):
        return set(typing.get_args(hint))
    return {hint}


def test_jurisdiction_code_rejects_venue_strings() -> None:
    """A venue string cannot be constructed into a jurisdiction.

    §9.8 names venue as the specific hazard: "speech at the party conference"
    is nominally a location and functionally an affiliation.  The constructor
    is where that stops being a matter of discipline.
    """
    for venue in (
        "speech at the party conference",
        "Likud HQ",
        "Knesset plenum",
        "il",
        "Israel",
        "",
    ):
        with pytest.raises(InvalidCode):
            JurisdictionCode(venue)


def test_jurisdiction_code_accepts_only_codes() -> None:
    assert JurisdictionCode("IL").value == "IL"
    assert JurisdictionCode("OECD").is_supranational
    assert not JurisdictionCode("IL").is_supranational


def test_claim_context_is_immutable() -> None:
    """Nothing downstream can rewrite the jurisdiction it was handed."""
    ctx = ClaimContext(
        jurisdiction=JurisdictionCode("IL"),
        language=LanguageCode("he"),
        stated_at=date(2026, 1, 1),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.jurisdiction = JurisdictionCode("US")  # type: ignore[misc]
