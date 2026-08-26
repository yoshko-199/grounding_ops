"""Claim-shape fuzzing — finding the defects the conformance suite cannot.

Every criterion in ``tests/conformance`` asks whether a specific guarantee
holds. None asks whether the engine behaves coherently on a claim nobody
thought to write down, and that turns out to be where the defects are.

Two were found by hand in one session, with the suite green at 376 tests:

* A time period was decomposed as a quantity, so ``"unemployment fell in
  2021"`` had the *year* compared against the unemployment rate and came back
  Contradicted. A true claim, labelled Substantially Inaccurate, with a full
  citation trail behind it.
* Two derivation triggers in sequence carved their flanks wrongly, so a
  superlative swallowed a later causal clause and a causal discharge named a
  time fragment as the effect of a government policy.

Neither is exotic. Both are ordinary claim shapes, and both were invisible to
the suite because fixture claims are written to exercise criteria rather than
to resemble anything: they carry one trigger, no year inside a period, no
superlative abutting a cause.

**What this checks, and what it cannot.** A fuzzer has no ground truth, so it
cannot ask whether a verdict is *right*. It asks whether the artifact is
self-consistent — whether the render survives, whether every numeral traces
somewhere, whether the ledger contradicts the routing note. Those are
properties that must hold for every claim whatever the answer, and both
defects above violate one.

**Where this sits.** Unlike :mod:`plugins.harvest`, this package imports the
engine, because driving the pipeline is the whole job. That is the difference
between an input plugin and a harness. The rule that still binds — and is
still asserted in ``tests/conformance/test_plugin_isolation.py`` — is the
other direction: nothing under ``engine/`` may reach anything under
``plugins/``.
"""

from plugins.shapes.invariants import INVARIANTS, Violation
from plugins.shapes.run import FuzzReport, fuzz
from plugins.shapes.shapes import Shape, generate, sample

__all__ = [
    "INVARIANTS",
    "FuzzReport",
    "Shape",
    "Violation",
    "fuzz",
    "generate",
    "sample",
]
