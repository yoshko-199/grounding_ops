"""AC-2 — No platform formatting.

Constraint: spec §7.2.  Output is never optimised for distribution.

§7.2's reasoning: "The moment output is optimised for distribution, users will
run verifications selectively until one produces the answer they wanted."
Most of this criterion is about absence, so most of it is a search.
"""

from __future__ import annotations

import inspect
import pathlib
import re

from engine.render.artifact import Artifact
from engine.render.figures import Payload

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = list((ROOT / "engine").rglob("*.py")) + list((ROOT / "cli").rglob("*.py"))

PLATFORM_NAMES = (
    "twitter", "tweet", "facebook", "instagram", "linkedin", "tiktok",
    "whatsapp", "telegram", "share_card", "og_image", "opengraph",
)


def _code_surface(path: pathlib.Path) -> set[str]:
    """Identifiers and non-docstring literals in a module.

    Docstrings and comments are excluded deliberately. AC-2 forbids a
    platform-named template *existing*, not the word appearing in prose that
    explains why one does not — and a scan that cannot tell the difference
    would make the codebase undocumentable on exactly the constraint it is
    checking.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))

    # Identify docstring *nodes*, not their text: ast.get_docstring returns a
    # dedented copy that no longer matches the literal in the tree.
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                docstrings.add(id(first.value))

    surface: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            surface.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            surface.add(node.attr.lower())
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            surface.add(node.name.lower())
        elif isinstance(node, ast.arg):
            surface.add(node.arg.lower())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                surface.add(node.value.lower())
    return surface


def test_no_platform_named_template_exists_in_the_tree() -> None:
    for path in SOURCE:
        surface = _code_surface(path)
        for name in PLATFORM_NAMES:
            offenders = [item for item in surface if name in item]
            assert not offenders, (
                f"{path.relative_to(ROOT)} defines or references {offenders!r}, "
                f"a platform-named surface"
            )


def test_no_output_path_takes_a_length_budget() -> None:
    """"if any output path takes a max-length parameter that truncates"."""
    for emitter in (Artifact.render, Artifact.to_dict, Payload.render):
        parameters = set(inspect.signature(emitter).parameters)
        for budget in ("max_length", "maxlen", "limit", "chars", "width", "truncate"):
            assert budget not in parameters


def test_no_share_affordance_exists() -> None:
    public = {name for name, _ in inspect.getmembers(Artifact) if not name.startswith("_")}
    for affordance in ("share", "copy", "post", "publish_to", "to_card", "permalink"):
        assert affordance not in public


def test_no_truncation_in_the_render_path() -> None:
    """Truncation is how a length budget arrives without being named one."""
    text = (ROOT / "engine" / "render" / "artifact.py").read_text(encoding="utf-8")
    assert "textwrap" not in text
    assert not re.search(r"\[:\s*\d+\s*\]", text), "a slice truncation in the render path"


def test_render_output_grows_with_content(registry, context, adapters, store) -> None:
    """A budgeted renderer would converge on a fixed size; this one does not."""
    from engine.pipeline import verify

    short = verify("prices rose in 2021", context, registry, adapters, store)
    long = verify(
        "prices rose over the last three years due to governmental incompetence",
        context, registry, adapters, store,
    )
    assert len(long.artifact.render()) > len(short.artifact.render())
