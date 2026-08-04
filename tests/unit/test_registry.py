"""The pack registry — immutability and the absence of a default jurisdiction."""

from __future__ import annotations

import pathlib
import shutil

import pytest

from engine.codes import JurisdictionCode
from engine.packs.registry import PackRegistry

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"


def test_registry_loads_the_fixture_jurisdiction() -> None:
    registry = PackRegistry.from_directory(PACKS)
    assert registry.jurisdictions == ("ZZ",)
    assert registry.covers(JurisdictionCode("ZZ"))


def test_unknown_jurisdiction_resolves_to_nothing() -> None:
    """§9.4's guardrail. No pack, no route, and no substitute.

    The absence of a pack is what lets the engine return Insufficient Data
    rather than improvise, and AC-14 calls this the criterion keeping
    generalisation from becoming dilution.
    """
    registry = PackRegistry.from_directory(PACKS)
    assert registry.get(JurisdictionCode("QQ")) is None
    assert not registry.covers(JurisdictionCode("QQ"))


def test_absent_jurisdiction_does_not_fall_back(tmp_path: pathlib.Path) -> None:
    """§9.8.3 — no default, no "most likely" inference, no operator setting.

    A default fails in the worst available way: every element genuinely
    Verified, every citation genuinely real, and the whole artifact about the
    wrong country.
    """
    registry = PackRegistry.from_directory(PACKS)
    assert registry.get(None) is None

    # Even with exactly one pack loaded, a null jurisdiction resolves to
    # nothing rather than to the only candidate.
    assert len(registry) == 1
    assert registry.get(None) is None


def test_registry_exposes_no_mutation_surface() -> None:
    """AC-3 — the configuration surfaces do not exist rather than refusing."""
    registry = PackRegistry.from_directory(PACKS)
    for forbidden in ("register", "add", "update", "unload", "set", "reload"):
        assert not hasattr(registry, forbidden), (
            f"PackRegistry exposes {forbidden!r}, a runtime mutation surface"
        )
    with pytest.raises(AttributeError):
        registry._packs = {}  # type: ignore[misc]


def test_loaded_mapping_cannot_be_mutated_through_the_registry() -> None:
    registry = PackRegistry.from_directory(PACKS)
    with pytest.raises(TypeError):
        registry._packs["ZZ"] = None  # type: ignore[index]


def test_two_packs_claiming_one_jurisdiction_is_an_error(
    tmp_path: pathlib.Path,
) -> None:
    """Silently preferring one would make routing depend on filesystem order."""
    shutil.copy(PACKS / "zz.toml", tmp_path / "zz.toml")
    shutil.copy(PACKS / "zz.toml", tmp_path / "zz-copy.toml")
    with pytest.raises(ValueError, match="two packs claim jurisdiction"):
        PackRegistry.from_directory(tmp_path)
