"""The packaging declared in pyproject.toml actually points at real code.

docs/plan.md's trial-hardening milestone: `pip install -e .` should let a
trial run `grounding-verify` instead of `PYTHONPATH=. python3 cli/verify.py`.
A `pip install -e .` was run by hand in a scratch venv while building this
(not repeated here — that is a slow, environment-mutating operation with no
place in the normal suite); what belongs in the suite is the cheap, static
half: that every declared console script names a module that exists and a
callable that is actually there and callable, so a typo in the entry point
string cannot ship unnoticed the way it would if this were only ever tested
by hand.
"""

from __future__ import annotations

import importlib
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_build_system_is_declared() -> None:
    """Without [build-system], `pip install -e .` has nothing to build with —
    the gap this milestone actually closed, not just the entry points."""
    data = _pyproject()
    assert "build-system" in data
    assert "setuptools" in data["build-system"]["requires"][0]


def test_every_console_script_resolves_to_a_real_callable() -> None:
    data = _pyproject()
    scripts = data["project"]["scripts"]
    assert scripts, "no console scripts declared"
    for name, target in scripts.items():
        module_name, _, attr = target.partition(":")
        assert attr, f"{name} = {target!r} is not a module:callable entry point"
        module = importlib.import_module(module_name)
        assert hasattr(module, attr), f"{module_name} has no attribute {attr!r}"
        assert callable(getattr(module, attr)), f"{module_name}.{attr} is not callable"


def test_console_scripts_only_cover_the_trial_facing_clis() -> None:
    """scripts/*.py are deliberately not entry points -- see pyproject.toml's
    own comment on why. This is the negative half of that decision."""
    data = _pyproject()
    scripts = data["project"]["scripts"]
    assert set(scripts) == {"grounding-verify", "grounding-show", "grounding-signoff"}


def test_packages_find_excludes_tests() -> None:
    """tests/ carries __init__.py at every level for pytest's own benefit and
    must not be picked up as an installable package alongside engine/cli/plugins."""
    data = _pyproject()
    find = data["tool"]["setuptools"]["packages"]["find"]
    assert "tests*" in find["exclude"]
