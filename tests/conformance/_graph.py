"""Static import-graph analysis over the engine package.

Two acceptance criteria are assertions about reachability rather than about
behaviour:

* **AC-6** — "assert by static analysis that ``claimant_identity`` is not
  reachable from any Stage 1-9 input", with the note that "an unused pathway
  is a latent failure, not a passing one".
* **AC-14** — "assert by static analysis that no retrieval path can reach a
  source that is not a declared custodian in a loaded pack".

Both need the same thing: the transitive set of modules a given module can
reach.  Runtime introspection cannot answer this, because a path that is
never taken in a passing test is exactly the latent failure AC-6 is warning
about.  So the graph is built from the source, not from an imported module.
"""

from __future__ import annotations

import ast
import pathlib
from functools import cache

ROOT = pathlib.Path(__file__).resolve().parents[2]


@cache
def _modules() -> dict[str, pathlib.Path]:
    """Every module in the engine package, by dotted name."""
    found: dict[str, pathlib.Path] = {}
    for path in sorted((ROOT / "engine").rglob("*.py")):
        rel = path.relative_to(ROOT).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts.pop()
        found[".".join(parts)] = path
    return found


@cache
def direct_imports(module: str) -> frozenset[str]:
    """Modules imported directly by ``module``, engine-internal and stdlib.

    ``from engine.ingest import identity`` is resolved to
    ``engine.ingest.identity`` where that names a real module, because the
    two forms are equivalent and a criterion that catches only one of them
    catches nothing.
    """
    path = _modules().get(module)
    if path is None:
        return frozenset()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    known = _modules()
    out: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                base = module.split(".")
                base = base[: len(base) - node.level] if node.level <= len(base) else []
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            if not prefix:
                continue
            out.add(prefix)
            for alias in node.names:
                candidate = f"{prefix}.{alias.name}"
                if candidate in known:
                    out.add(candidate)
    return frozenset(out)


def reachable(module: str) -> frozenset[str]:
    """Transitive closure of imports from ``module``, following engine modules.

    Non-engine imports (stdlib, third party) are recorded but not followed —
    AC-14 needs to see that ``urllib`` was imported, not to walk into it.
    """
    seen: set[str] = set()
    stack = [module]
    known = _modules()
    while stack:
        current = stack.pop()
        for dep in direct_imports(current):
            if dep in seen:
                continue
            seen.add(dep)
            if dep in known:
                stack.append(dep)
    return frozenset(seen)


def modules_under(package: str) -> list[str]:
    """Every engine module inside ``package``, including the package itself."""
    return sorted(
        name
        for name in _modules()
        if name == package or name.startswith(f"{package}.")
    )
