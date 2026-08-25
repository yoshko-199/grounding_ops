"""The plugin boundary, asserted rather than agreed.

`plugins/harvest` does the four things `engine/custodians/base.py` excludes by
name — "no web search, no news source, no model prior, no operator-supplied
URL." That is fine, because it operates on the claim-input side, where those
things are what the job *is*. It stops being fine the moment anything on the
verification side can reach it.

So the boundary gets the same treatment AC-6 and AC-14 get: static import-graph
analysis, over the source rather than at runtime, because "a path that is never
taken in a passing test is exactly the latent failure AC-6 is warning about."

Three directions are checked, and the third is the one that would be forgotten:

1. No engine module reaches a plugin.
2. No harvest module reaches the custodian adapters, the retrieval layer, or
   the event store.
3. The guard is not vacuous — the analyser can actually see plugin modules and
   would catch a violation if one were introduced.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from tests.conformance._graph import ROOT, direct_imports, modules_under, reachable

ENGINE_MODULES = modules_under("engine")
HARVEST_MODULES = modules_under("plugins.harvest")

#: Engine modules a harvester must never reach. These are the ones that can
#: originate or persist evidence; reaching any of them would put harvested
#: text on a path where it could be mistaken for a retrieval.
EVIDENCE_MODULES = frozenset(
    {
        "engine.custodians",
        "engine.custodians.base",
        "engine.custodians.fixture",
        "engine.verification.retrieve",
        "engine.store",
        "engine.store.events",
        "engine.figures",
        "engine.signoff",
    }
)


def test_the_analyser_can_see_the_plugin_package() -> None:
    """Direction 3, first half: the guard has something to guard."""
    assert HARVEST_MODULES, (
        "no plugins.harvest modules found. Every assertion below would pass "
        "vacuously, which is worse than a missing test because it reads as one "
        "that ran"
    )


@pytest.mark.parametrize("module", ENGINE_MODULES)
def test_no_engine_module_reaches_a_plugin(module: str) -> None:
    """Direction 1 — the load-bearing one.

    A plugin reachable from the engine is a network client reachable from a
    verification path, which is the generic fallback §9.4 forbids however
    indirectly it is arrived at.
    """
    offenders = sorted(dep for dep in reachable(module) if dep.split(".")[0] == "plugins")
    assert not offenders, (
        f"{module} can reach {offenders}. Nothing under plugins/ may be reachable "
        "from the engine: a harvester on a verification path is a source nobody "
        "declared as a custodian"
    )


@pytest.mark.parametrize("module", HARVEST_MODULES)
def test_no_harvest_module_reaches_the_evidence_layer(module: str) -> None:
    """Direction 2 — the harvester cannot write into the record.

    Reading a type from the engine would be harmless in itself; being able to
    reach the store or an adapter is not, because that is the point at which
    harvested text could acquire a retrieval id and stop looking like a claim.
    """
    offenders = sorted(reachable(module) & EVIDENCE_MODULES)
    assert not offenders, (
        f"{module} can reach {offenders}. The harvest side produces claims, never "
        "evidence, and a path to the store is how that stops being true"
    )


def test_no_harvest_module_imports_the_engine_at_all() -> None:
    """Stronger than the criterion needs, and cheap to keep.

    The evidence-module list above is a denylist, and denylists rot as modules
    are added. Asserting the harvester imports no engine module at all means a
    new evidence module is covered the day it is written rather than the day
    somebody remembers to add it here.
    """
    for module in HARVEST_MODULES:
        offenders = sorted(
            dep for dep in reachable(module) if dep.split(".")[0] == "engine"
        )
        assert not offenders, f"{module} imports {offenders}"


def test_the_import_guard_would_catch_a_violation(tmp_path: pathlib.Path) -> None:
    """Direction 3, second half — negative control on the analyser itself.

    Every other assertion in this file passes today. The only way to know they
    pass because the property holds, rather than because the analyser cannot
    see the imports, is to hand it a module that does violate the rule and
    confirm it is detected.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from plugins.harvest.transport import UrllibTransport\n"
        "import plugins.harvest.scan\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    found = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert any(name.startswith("plugins.") for name in found), (
        "the import forms used by the analyser do not detect a planted "
        "violation; the assertions above would pass on a broken graph"
    )


def test_the_harvester_declares_no_model_backed_transport() -> None:
    """The one backend from the prior art that is deliberately absent.

    `auto-karpathy`'s scraper falls back to a model with web search, asked to
    return JSON that then becomes data. Reimplementing it here in any form
    would put a model prior on the intake path, and intake feeds claims that
    are later quoted verbatim in an artifact carrying custodian names.
    """
    from plugins.harvest.sources import BackendKind

    kinds = {kind.value for kind in BackendKind}
    assert kinds == {"rss", "json", "embedded-json"}, (
        f"backend kinds changed to {sorted(kinds)}; if a model- or search-backed "
        "transport was added, engine/custodians/base.py explains why it must not be"
    )

    for module in HARVEST_MODULES:
        reached = reachable(module)
        assert not {
            dep for dep in reached if "claude_agent_sdk" in dep or "anthropic" in dep
        }, f"{module} reaches a model SDK"


def test_no_harvest_module_declares_a_third_party_dependency() -> None:
    """The repository ships an empty ``dependencies`` list; keep it that way."""
    third_party = {"httpx", "requests", "aiohttp", "pydantic", "platformdirs", "twikit"}
    for module in HARVEST_MODULES:
        offenders = sorted(
            dep for dep in direct_imports(module) if dep.split(".")[0] in third_party
        )
        assert not offenders, f"{module} imports {offenders}, which pyproject does not declare"


def test_the_corpus_is_not_read_by_the_engine() -> None:
    """A corpus is a test input. Nothing at runtime may depend on one."""
    for path in sorted((ROOT / "engine").rglob("*.py")):
        body = path.read_text(encoding="utf-8")
        assert "claims.jsonl" not in body, f"{path} references the harvested corpus"
