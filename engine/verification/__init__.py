"""Stages 1-9 — the claimant-blind verification path.

Nothing in this package may import engine.ingest.identity, transitively or
otherwise.  That is not a style rule: AC-6 asserts it over the import graph
in tests/conformance/test_ac06.py, and the assertion is what converts "we are
non-partisan" from a claim about intent into a property of the build.
"""
