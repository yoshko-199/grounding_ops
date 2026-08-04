"""Shared fixtures for the conformance suite."""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.packs.registry import PackRegistry
from engine.store.events import RetrievalStore

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"


@pytest.fixture
def registry() -> PackRegistry:
    return PackRegistry.from_directory(PACKS)


@pytest.fixture
def pack(registry: PackRegistry):
    return registry.get(JurisdictionCode("ZZ"))


@pytest.fixture
def lexicon(pack):
    return pack.lexicon(LanguageCode("en"))


@pytest.fixture
def adapters():
    return build_fixture_custodians()


@pytest.fixture
def store():
    s = RetrievalStore()
    yield s
    s.close()


@pytest.fixture
def context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )
