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
    own comment on why. This is the negative half of that decision. The web
    UI is trial-facing, so it is the fourth."""
    data = _pyproject()
    scripts = data["project"]["scripts"]
    assert set(scripts) == {
        "grounding-verify", "grounding-show", "grounding-signoff", "grounding-serve",
    }


def test_packages_find_excludes_tests() -> None:
    """tests/ carries __init__.py at every level for pytest's own benefit and
    must not be picked up as an installable package alongside engine and cli."""
    data = _pyproject()
    find = data["tool"]["setuptools"]["packages"]["find"]
    assert "tests*" in find["exclude"]


# -- the packs default, which packaging made load-bearing --------------------


def test_the_default_packs_directory_is_anchored_to_the_repository() -> None:
    """Console scripts made running from outside the checkout normal, and a
    cwd-relative default resolves to nothing there. The failure was silent:
    an empty registry renders "no jurisdiction could be established", which
    is the right sentence for an uncovered claim and the wrong one for packs
    that were never found."""
    import cli.verify

    default = pathlib.Path(cli.verify.DEFAULT_PACKS)
    assert default.is_absolute()
    assert default.is_relative_to(cli.verify.ROOT)
    assert any(default.glob("*.toml")), "the anchored default points at no packs"


def test_a_missing_packs_directory_exits_2_rather_than_verifying(tmp_path, capsys) -> None:
    from cli.verify import main

    code = main(
        ["prices rose", "--jurisdiction", "ZZ", "--store", ":memory:",
         "--packs", str(tmp_path / "not-there")]
    )
    assert code == 2
    assert "no pack directory" in capsys.readouterr().err


def test_an_empty_packs_directory_exits_2_rather_than_verifying(tmp_path, capsys) -> None:
    from cli.verify import main

    empty = tmp_path / "empty"
    empty.mkdir()
    code = main(
        ["prices rose", "--jurisdiction", "ZZ", "--store", ":memory:", "--packs", str(empty)]
    )
    assert code == 2
    assert "no pack files" in capsys.readouterr().err


def test_the_wheel_would_not_ship_the_network_capable_plugins_package() -> None:
    """`plugins.harvest` is the one package in the tree that may reach the
    network. No console script imports it, and the tooling that does runs
    from a checkout, so it has no reason to be in an installed environment."""
    data = _pyproject()
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert include == ["engine*", "cli*"]
    assert not any(pattern.startswith("plugins") for pattern in include)
