"""Custodian pack structures — interface §3.1 to §3.6.

A pack is data, not code (interface §1).  Adding a jurisdiction must never
require changing the pipeline, so nothing in this module knows anything about
any particular country, institution, or dataset.

Every structure here is frozen.  Interface §2 requires packs to be
non-configurable at runtime, and AC-3 tests mutation through "every
configuration surface" — the cheapest way to pass that is for the loaded
objects to have no setters at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from engine.codes import JurisdictionCode, LanguageCode
from engine.elements import DerivationOperation


class SurfaceCategory(Enum):
    """Interface v1.4, §3.6.  A closed set of language-general surface forms.

    Not derivation operations — nothing here discharges into a derived
    element. ``RISE``/``FALL`` decide an element's direction (§9.2) and scope
    a claim's quantitative content (§4 Stage 1); ``PREDICTION`` decides
    whether a claim is about the future with no past anchor. All three used
    to be English-only regexes in :mod:`engine.verification.patterns`, which
    is exactly the "pipeline hardcodes one language" failure interface §9.4
    forbids for everything else. Closed and versioned with the interface for
    the same reason :class:`DerivationOperation` is: an implementer able to
    invent a fourth category could shape what the pipeline sees without a
    pack-review trail.
    """

    RISE = "rise"
    FALL = "fall"
    PREDICTION = "prediction"


class BreakKind(Enum):
    """Interface §3.5."""

    BASE_YEAR = "base_year"
    METHODOLOGY = "methodology"
    DEFINITION = "definition"
    CLASSIFICATION = "classification"
    COVERAGE = "coverage"


@dataclass(frozen=True, slots=True)
class SeriesBreak:
    """A declared fracture in a series.

    ``custodian_notice_ref`` is required and may not be empty.  Interface §3.5
    is explicit about why: "a break the engine inferred but the custodian
    never announced is a *flag*, not a register entry."  §9.5's three
    detection heuristics can raise suspicion; none may populate this.
    """

    effective_date: date
    kind: BreakKind
    custodian_notice_ref: str
    linked_series_available: bool
    linked_series_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class Custodian:
    """Interface §3.2.  An institution with a mandate to publish the figure.

    Not "a good source".  An outlet that reports a figure is not its
    custodian, and the distinction is what AC-14 calls the thing keeping
    generalisation from becoming dilution.
    """

    id: str
    name: str
    mandate: str
    cadence: str
    revision_policy: str
    access_method: str
    integrity_annotation: str


@dataclass(frozen=True, slots=True)
class Measure:
    """Interface §3.3.  The measure, not the source, is the unit of correctness.

    ``published_precision`` drives the tolerance bands (§9.2) and is the one
    numeric field a pack legitimately carries: it describes the custodian's
    reporting precision, not a value of the series.
    """

    id: str
    name: str
    definition: str
    custodian_id: str
    series_identifier: str
    unit: str
    published_precision: float
    discrete: bool
    known_confusions: tuple[str, ...]
    admissible_baselines: tuple[str, ...]
    admissible_windows: tuple[str, ...]
    admissible_source_ref: str
    series_breaks: tuple[SeriesBreak, ...] = ()

    @property
    def sweep_can_run(self) -> bool:
        """Whether §9.3's sweep has anything to vary.

        A measure with no declared alternatives caps every verdict on it at
        Indeterminate (AC-11).  That is the pack interface behaving as
        designed: an incomplete pack degrades to conservative outcomes rather
        than routing confidently on partial knowledge.
        """
        return bool(self.admissible_baselines) or bool(self.admissible_windows)


@dataclass(frozen=True, slots=True)
class RoutingRule:
    """Interface §3.4.  Why this custodian and not another.

    ``no_alternative_custodian`` is the declaration AC-4 requires: empty
    alternatives are admissible "only where the pack declares no alternative
    custodian exists for that measure", and this is that declaration.  A
    routing table showing only winners is indistinguishable from one built
    backwards from preferred answers.
    """

    measure_id: str
    custodian_id: str
    rationale: str
    alternatives_considered: tuple[str, ...] = ()
    no_alternative_custodian: bool = False


@dataclass(frozen=True, slots=True)
class Lexicon:
    """Interface §3.6, new in v1.1.

    Spec §9.7.2 triggers derivation on connective phrases and §9.9 composes
    reconstructions from connectives.  Both are language-specific, and a pack
    that declares a language without a lexicon for it under-fires silently on
    every claim in that language.
    """

    language: LanguageCode
    derivation_triggers: dict[DerivationOperation, tuple[str, ...]]
    composition_connectives: tuple[str, ...]
    forbidden_connectives: tuple[str, ...]
    element_slot_order: tuple[str, ...]
    # Interface v1.4. Required, on the same footing as `derivation_triggers`
    # above and for the same reason: no default, so every direct construction
    # (loader and test) states it explicitly rather than inheriting silence.
    # Every language a pack declares must say what its rise/fall/prediction
    # surface forms are, instead of the pipeline silently reaching for
    # patterns.py's English list. Silent inheritance is exactly the failure
    # this closes — a Hebrew claim decomposed against English direction words
    # doesn't error, it just quietly finds none, which looks identical to a
    # claim that had no direction in it.
    surface_vocabulary: dict[SurfaceCategory, tuple[str, ...]]
    # Interface v1.2. Pack data, versioned and reviewable, on the same footing
    # as the trigger lists themselves (AC-3). Off unless a pack says otherwise.
    fuzzy_trigger_matching: bool = False
    # Interface v1.3. The demonyms and short forms a claim in this language may
    # use for the jurisdiction — "Israel", not just "IL". §9.8.2 rule 1 binds a
    # claim that names its own jurisdiction "because it needs no provenance at
    # all", but the rule was implemented against the header's bare code, which
    # real claims almost never carry. Optional and empty by default: a pack
    # that declares none simply keeps today's behaviour, falling through to
    # rule 2 — conservative, not broken, the same failure mode §9.8.3 already
    # accepts everywhere else a rule does not fire.
    names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class JurisdictionHeader:
    """Interface §3.1."""

    jurisdiction_id: JurisdictionCode
    languages: tuple[LanguageCode, ...]
    authority_basis: str
    pack_version: str
    maintainer: str


@dataclass(frozen=True, slots=True)
class Pack:
    """A loaded, validated custodian pack."""

    header: JurisdictionHeader
    custodians: tuple[Custodian, ...]
    measures: tuple[Measure, ...]
    routing_rules: tuple[RoutingRule, ...]
    lexicons: tuple[Lexicon, ...]
    source_path: str = ""
    _by_measure: dict[str, Measure] = field(default_factory=dict, compare=False)
    _by_custodian: dict[str, Custodian] = field(default_factory=dict, compare=False)
    _routes: dict[str, RoutingRule] = field(default_factory=dict, compare=False)
    _lexicons: dict[str, Lexicon] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        self._by_measure.update({m.id: m for m in self.measures})
        self._by_custodian.update({c.id: c for c in self.custodians})
        self._routes.update({r.measure_id: r for r in self.routing_rules})
        self._lexicons.update({str(lx.language): lx for lx in self.lexicons})

    @property
    def jurisdiction(self) -> JurisdictionCode:
        return self.header.jurisdiction_id

    @property
    def version(self) -> str:
        return self.header.pack_version

    def measure(self, measure_id: str) -> Measure | None:
        return self._by_measure.get(measure_id)

    def custodian(self, custodian_id: str) -> Custodian | None:
        return self._by_custodian.get(custodian_id)

    def route_for(self, measure_id: str) -> RoutingRule | None:
        return self._routes.get(measure_id)

    def lexicon(self, language: LanguageCode) -> Lexicon | None:
        return self._lexicons.get(str(language))
