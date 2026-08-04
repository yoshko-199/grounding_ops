"""AC-3 — Non-configurability.

Constraint: spec §7.3.  Tolerance thresholds and routing tables are
inspectable and versioned, not operator-configurable.

"Then attempt mutation through every configuration surface — runtime API,
admin endpoint, settings file, environment variable, feature flag, database
write, CLI argument. Assert every attempt fails."

§7.3's reasoning is the point: "Partisanship enters most invisibly through
source selection."
"""

from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys
from decimal import Decimal

import pytest

from engine.elements import ElementKind
from engine.packs.registry import PackRegistry
from engine.verification import tolerance

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULE_MODULES = [
    ROOT / "engine" / "verification" / "tolerance.py",
    ROOT / "engine" / "packs" / "loader.py",
    ROOT / "engine" / "packs" / "registry.py",
    ROOT / "engine" / "verification" / "route.py",
]


def test_no_rule_module_reads_the_environment() -> None:
    """An env var is a configuration surface like any other."""
    for path in RULE_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("getenv", "environ"):
                pytest.fail(f"{path.relative_to(ROOT)} reads the environment")
            if isinstance(node, ast.Name) and node.id in ("getenv", "environ"):
                pytest.fail(f"{path.relative_to(ROOT)} reads the environment")


def test_an_environment_variable_cannot_move_a_threshold(monkeypatch) -> None:
    monkeypatch.setenv("TOLERANCE_BAND_A_RELATIVE", "0.99")
    monkeypatch.setenv("GROUNDING_OPS_BAND_A", "0.99")
    import importlib

    importlib.reload(tolerance)
    assert tolerance.BAND_A_RELATIVE == Decimal("0.005")


def test_the_band_function_takes_no_configuration_parameter() -> None:
    import inspect

    parameters = set(inspect.signature(tolerance.band_for).parameters)
    for surface in ("config", "settings", "options", "overrides", "profile", "session"):
        assert surface not in parameters


def test_a_cli_argument_cannot_move_a_threshold() -> None:
    """"attempt mutation through every configuration surface [...] CLI argument"."""
    result = subprocess.run(
        [sys.executable, "cli/verify.py", "prices rose in 2021",
         "--jurisdiction", "ZZ", "--packs", "packs/fixture",
         "--tolerance-band-a", "0.99"],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


def test_a_loaded_pack_cannot_be_mutated() -> None:
    import dataclasses

    registry = PackRegistry.from_directory(ROOT / "packs" / "fixture")
    pack = registry.get(__import__("engine.codes", fromlist=["JurisdictionCode"]).JurisdictionCode("ZZ"))
    measure = pack.measure("price_index")

    with pytest.raises(dataclasses.FrozenInstanceError):
        measure.published_precision = 99.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        pack.route_for("price_index").custodian_id = "somewhere_else"  # type: ignore[misc]


def test_a_pack_carries_a_version_and_the_router_records_it(registry, context) -> None:
    """"assert that a legitimate change requires a pack version bump, and that
    the bump is recorded in routing_log.pack_version"."""
    from engine.verification.route import route

    decision = route("prices rose in 2021", context, registry)
    assert decision.pack_version
    assert decision.pack.version == decision.pack_version


def test_a_pack_without_a_version_does_not_load(tmp_path: pathlib.Path) -> None:
    from engine.packs.loader import validate

    source = (ROOT / "packs" / "fixture" / "zz.toml").read_text(encoding="utf-8")
    broken = tmp_path / "unversioned.toml"
    broken.write_text(source.replace('pack_version = "1.0.0-fixture"', 'pack_version = ""'),
                      encoding="utf-8")
    assert "pack_version" in "\n".join(validate(broken).failures)


def test_the_binary_overrides_cannot_be_disabled() -> None:
    """A superlative cannot be turned into a numeric comparison by any input."""
    for kind in (ElementKind.SUPERLATIVE, ElementKind.DIRECTION):
        with pytest.raises(ValueError):
            tolerance.band_for(
                Decimal("1"), Decimal("1"),
                published_precision=Decimal("0.1"), discrete=False, kind=kind,
            )
