"""Pack parsing and the interface §6 validation checklist.

Every item on the checklist is pass/fail, and this module implements them as
such.  A pack failing any item does not load.  Interface §3 states the reason
plainly: "a partial pack is worse than no pack, because it routes some claims
and silently drops others" — the second half is what makes it worse, since a
pack that routes nothing is visibly broken and a pack that routes half of
what it should looks like it is working.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.codes import InvalidCode, JurisdictionCode, LanguageCode
from engine.elements import DerivationOperation
from engine.packs.schema import (
    BreakKind,
    Custodian,
    JurisdictionHeader,
    Lexicon,
    Measure,
    Pack,
    RoutingRule,
    SeriesBreak,
)

REQUIRED_BLOCKS = ("header", "custodians", "measures", "routing_rules", "lexicons")

# Terms that may never appear in composition_connectives.  Interface §3.6
# and spec §9.9.2: the allowlist admits enumeration and sequencing, and
# nothing causal, evaluative, concessive, or explanatory.
_DISALLOWED_IN_COMPOSITION = (
    "because",
    "due to",
    "caused",
    "thanks to",
    "as a result",
    "so that",
    "therefore",
    "hence",
    "which shows",
    "meaning",
    "although",
    "despite",
    "however",
    "only",
    "even",
)

# A statistic looks like a number carrying a unit of measurement.  Scanned
# over free-text fields only: published_precision is a typed numeric field
# describing the custodian's reporting precision, not a value of the series,
# and scanning it would flag the one number a pack legitimately holds.
_FIGURE = re.compile(
    r"(?<![\w])(\d{1,3}(?:,\d{3})+|\d+\.\d+|\d+)\s*"
    r"(%|pp|bn|billion|million|trillion|₪|\$|€|£|index points?)",
    re.I,
)


class PackInvalid(Exception):
    """Raised when a pack fails the interface §6 checklist."""

    def __init__(self, path: str, failures: list[str]) -> None:
        self.path = path
        self.failures = failures
        detail = "\n".join(f"  - {f}" for f in failures)
        super().__init__(f"{path} failed pack validation:\n{detail}")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    path: str
    failures: tuple[str, ...]

    @property
    def admitted(self) -> bool:
        return not self.failures


def load(path: str | Path) -> Pack:
    """Parse and validate a pack, or raise :class:`PackInvalid`."""
    path = Path(path)
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    pack, failures = _build(raw, str(path))
    if failures:
        raise PackInvalid(str(path), failures)
    assert pack is not None
    return pack


def validate(path: str | Path) -> ValidationReport:
    """Run the checklist without raising, for tooling and tests."""
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return ValidationReport(str(path), (f"unparseable TOML: {exc}",))
    _, failures = _build(raw, str(path))
    return ValidationReport(str(path), tuple(failures))


def _build(raw: dict[str, Any], path: str) -> tuple[Pack | None, list[str]]:
    failures: list[str] = []

    # Checklist item 1 — all five required blocks present.
    for block in REQUIRED_BLOCKS:
        if not raw.get(block):
            failures.append(f"required block missing or empty: [{block}]")
    if failures:
        return None, failures

    header, header_failures = _header(raw["header"])
    failures.extend(header_failures)

    custodians = tuple(_custodian(c, failures) for c in raw["custodians"])
    measures = tuple(_measure(m, failures) for m in raw["measures"])
    routes = tuple(_route(r, failures) for r in raw["routing_rules"])
    lexicons = tuple(_lexicon(lx, failures) for lx in raw["lexicons"])

    if header is not None:
        failures.extend(_cross_checks(header, custodians, measures, routes, lexicons))
    failures.extend(_no_figures(raw))
    failures.extend(_no_markup(raw))

    if failures or header is None:
        return None, failures
    return (
        Pack(
            header=header,
            custodians=custodians,
            measures=measures,
            routing_rules=routes,
            lexicons=lexicons,
            source_path=path,
        ),
        failures,
    )


def _header(raw: dict[str, Any]) -> tuple[JurisdictionHeader | None, list[str]]:
    failures: list[str] = []
    for key in ("jurisdiction_id", "languages", "authority_basis", "pack_version", "maintainer"):
        if not raw.get(key):
            failures.append(f"header.{key} is required and may not be empty")
    if failures:
        return None, failures
    try:
        jurisdiction = JurisdictionCode(raw["jurisdiction_id"])
    except InvalidCode as exc:
        return None, [f"header.jurisdiction_id: {exc}"]
    try:
        languages = tuple(LanguageCode(code) for code in raw["languages"])
    except InvalidCode as exc:
        return None, [f"header.languages: {exc}"]
    return (
        JurisdictionHeader(
            jurisdiction_id=jurisdiction,
            languages=languages,
            authority_basis=raw["authority_basis"],
            pack_version=raw["pack_version"],
            maintainer=raw["maintainer"],
        ),
        [],
    )


def _custodian(raw: dict[str, Any], failures: list[str]) -> Custodian:
    """Checklist item 2 — mandate, cadence, revision policy, integrity annotation.

    ``integrity_annotation`` is the field interface §3.2 calls "most likely to
    be skipped and the one that matters most", and it may not be empty: a
    maintainer with nothing to report writes `none known` explicitly, so that
    its absence is a deliberate statement rather than an oversight.
    """
    cid = raw.get("id", "<unnamed>")
    for key in ("id", "name", "mandate", "cadence", "revision_policy",
                "access_method", "integrity_annotation"):
        if not str(raw.get(key, "")).strip():
            failures.append(f"custodian {cid!r}: {key} is required and may not be empty")
    return Custodian(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        mandate=raw.get("mandate", ""),
        cadence=raw.get("cadence", ""),
        revision_policy=raw.get("revision_policy", ""),
        access_method=raw.get("access_method", ""),
        integrity_annotation=raw.get("integrity_annotation", ""),
    )


def _measure(raw: dict[str, Any], failures: list[str]) -> Measure:
    """Checklist item 4, plus the §3.5 break register requirement."""
    mid = raw.get("id", "<unnamed>")
    for key in ("id", "name", "definition", "custodian_id", "series_identifier",
                "unit", "admissible_source_ref"):
        if not str(raw.get(key, "")).strip():
            failures.append(f"measure {mid!r}: {key} is required and may not be empty")
    if raw.get("published_precision") is None:
        failures.append(f"measure {mid!r}: published_precision is required (drives §9.2 bands)")
    if raw.get("discrete") is None:
        failures.append(f"measure {mid!r}: discrete is required (drives exact-match tolerance)")
    if not raw.get("known_confusions"):
        failures.append(
            f"measure {mid!r}: known_confusions[] may not be empty; write 'none known' "
            "explicitly where the measure genuinely has no near neighbour"
        )

    breaks: list[SeriesBreak] = []
    for entry in raw.get("series_breaks", []):
        # Checklist item 6 — every break cites a custodian notice.
        if not str(entry.get("custodian_notice_ref", "")).strip():
            failures.append(
                f"measure {mid!r}: a series break cites no custodian_notice_ref. "
                "A break the engine inferred but the custodian never announced is a "
                "suspicion, not a fact about the series (§9.5)"
            )
        try:
            kind = BreakKind(entry.get("kind", ""))
        except ValueError:
            failures.append(f"measure {mid!r}: unknown break kind {entry.get('kind')!r}")
            continue
        linked = bool(entry.get("linked_series_available", False))
        identifier = entry.get("linked_series_identifier")
        if linked and not identifier:
            failures.append(
                f"measure {mid!r}: break declares a linked series but names no "
                "linked_series_identifier"
            )
        breaks.append(
            SeriesBreak(
                effective_date=entry["effective_date"],
                kind=kind,
                custodian_notice_ref=entry.get("custodian_notice_ref", ""),
                linked_series_available=linked,
                linked_series_identifier=identifier,
            )
        )

    return Measure(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        definition=raw.get("definition", ""),
        custodian_id=raw.get("custodian_id", ""),
        series_identifier=raw.get("series_identifier", ""),
        unit=raw.get("unit", ""),
        published_precision=float(raw.get("published_precision") or 0.0),
        discrete=bool(raw.get("discrete", False)),
        known_confusions=tuple(raw.get("known_confusions", ())),
        admissible_baselines=tuple(raw.get("admissible_baselines", ())),
        admissible_windows=tuple(raw.get("admissible_windows", ())),
        admissible_source_ref=raw.get("admissible_source_ref", ""),
        series_breaks=tuple(breaks),
    )


def _route(raw: dict[str, Any], failures: list[str]) -> RoutingRule:
    """Checklist item 5, and AC-4's declaration requirement."""
    mid = raw.get("measure_id", "<unnamed>")
    for key in ("measure_id", "custodian_id", "rationale"):
        if not str(raw.get(key, "")).strip():
            failures.append(f"routing rule for {mid!r}: {key} is required and may not be empty")
    alternatives = tuple(raw.get("alternatives_considered", ()))
    declared_none = bool(raw.get("no_alternative_custodian", False))
    if not alternatives and not declared_none:
        failures.append(
            f"routing rule for {mid!r}: alternatives_considered[] is empty without "
            "no_alternative_custodian = true. AC-4 admits emptiness only where the "
            "pack declares no alternative exists"
        )
    if alternatives and declared_none:
        failures.append(
            f"routing rule for {mid!r}: declares no_alternative_custodian while also "
            "listing alternatives"
        )
    return RoutingRule(
        measure_id=raw.get("measure_id", ""),
        custodian_id=raw.get("custodian_id", ""),
        rationale=raw.get("rationale", ""),
        alternatives_considered=alternatives,
        no_alternative_custodian=declared_none,
    )


def _lexicon(raw: dict[str, Any], failures: list[str]) -> Lexicon | None:
    """Interface §3.6 — the v1.1 block."""
    try:
        language = LanguageCode(raw.get("language", ""))
    except InvalidCode as exc:
        failures.append(f"lexicon: {exc}")
        return None

    triggers_raw = raw.get("derivation_triggers", {})
    triggers: dict[DerivationOperation, tuple[str, ...]] = {}
    for operation in DerivationOperation:
        if operation.value not in triggers_raw:
            failures.append(
                f"lexicon {language}: derivation_triggers is missing "
                f"{operation.value!r}. All five operations must be keyed; declare an "
                "empty list explicitly where the operation has no trigger in this language"
            )
            continue
        triggers[operation] = tuple(triggers_raw[operation.value])

    composition = tuple(raw.get("composition_connectives", ()))
    forbidden = tuple(raw.get("forbidden_connectives", ()))
    if not composition:
        failures.append(f"lexicon {language}: composition_connectives may not be empty")
    if not forbidden:
        failures.append(
            f"lexicon {language}: forbidden_connectives may not be empty. This is where "
            "AC-15's 'equivalents in each pack's declared languages' live; an empty list "
            "provides no protection on claims in this language"
        )
    for connective in composition:
        lowered = connective.lower()
        for banned in _DISALLOWED_IN_COMPOSITION:
            if banned in lowered:
                failures.append(
                    f"lexicon {language}: composition_connectives contains {connective!r}, "
                    f"which is {banned!r}. §9.9.2 admits enumeration and sequencing only"
                )
    overlap = set(c.lower() for c in composition) & set(f.lower() for f in forbidden)
    if overlap:
        failures.append(
            f"lexicon {language}: {sorted(overlap)} appear in both composition_connectives "
            "and forbidden_connectives"
        )
    if not raw.get("element_slot_order"):
        failures.append(f"lexicon {language}: element_slot_order is required (§9.9.1)")

    return Lexicon(
        language=language,
        derivation_triggers=triggers,
        composition_connectives=composition,
        forbidden_connectives=forbidden,
        element_slot_order=tuple(raw.get("element_slot_order", ())),
        fuzzy_trigger_matching=bool(raw.get("fuzzy_trigger_matching", False)),
        # Interface v1.3, optional. Absent means "no declared name in this
        # language", which is a conservative under-fire of §9.8.2 rule 1, not
        # a validation failure — see the field's docstring in schema.py.
        names=tuple(raw.get("names", ())),
    )


def _cross_checks(
    header: JurisdictionHeader,
    custodians: tuple[Custodian, ...],
    measures: tuple[Measure, ...],
    routes: tuple[RoutingRule, ...],
    lexicons: tuple[Lexicon | None, ...],
) -> list[str]:
    failures: list[str] = []
    custodian_ids = {c.id for c in custodians}
    measure_ids = {m.id for m in measures}

    # Checklist item 3 — every measure resolves to a declared custodian.
    for measure in measures:
        if measure.custodian_id not in custodian_ids:
            failures.append(
                f"measure {measure.id!r} routes to undeclared custodian "
                f"{measure.custodian_id!r}"
            )

    # Checklist item 7 — no routing rule points outside the declared custodians.
    # This is the mechanical form of "no generic fallback" (AC-14): a route to
    # something that is not a custodian of record is the dilution the whole
    # interface exists to prevent.
    for route in routes:
        if route.custodian_id not in custodian_ids:
            failures.append(
                f"routing rule for {route.measure_id!r} points at "
                f"{route.custodian_id!r}, which is not a declared custodian"
            )
        if route.measure_id not in measure_ids:
            failures.append(
                f"routing rule names undeclared measure {route.measure_id!r}"
            )

    # A measure with no routing rule is interface §4.1's third failure: it
    # resolves to Insufficient Data and is a pack defect to be filed.
    routed = {r.measure_id for r in routes}
    for measure in measures:
        if measure.id not in routed:
            failures.append(
                f"measure {measure.id!r} has no routing rule. Interface §4.1 makes this "
                "Insufficient Data at runtime and a pack defect here"
            )

    # Checklist items 10 and 11 — languages and lexicons correspond exactly.
    declared = {str(language) for language in header.languages}
    provided = {str(lx.language) for lx in lexicons if lx is not None}
    for missing in sorted(declared - provided):
        failures.append(
            f"language {missing!r} is declared in the header with no lexicon entry. "
            "Derivation would under-fire silently on every claim in that language"
        )
    for extra in sorted(provided - declared):
        failures.append(f"lexicon declares language {extra!r}, absent from header.languages")

    return failures


# Markup a pack must not carry. Pack prose is copied verbatim into
# plain-text artifacts — a measure's first known confusion becomes the framing
# caveat on every citation line for that measure — so emphasis markers render
# as literal characters beside a custodian's name. Caught at load rather than
# left to a reviewer's eye, because it looks correct in the source file and
# only looks wrong in the output.
_MARKUP = re.compile(r"\*\*|__|`|<[a-z/][^>]*>", re.I)


def _no_markup(raw: dict[str, Any]) -> list[str]:
    """Pack text is rendered as plain text, so markup in it is a defect.

    Found by review after the euro and sterling measures shipped with
    ``**Cross-derived, not sampled.**`` as their first known confusion, which
    put literal asterisks on every citation those measures produced.
    """
    failures: list[str] = []

    def walk(node: Any, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{trail}.{key}" if trail else key)
        elif isinstance(node, (list, tuple)):
            for i, value in enumerate(node):
                walk(value, f"{trail}[{i}]")
        elif isinstance(node, str):
            match = _MARKUP.search(node)
            if match:
                failures.append(
                    f"{trail} contains markup: {match.group(0)!r}. Pack text renders "
                    "as plain text beside a custodian's name, so emphasis markers "
                    "reach the reader as literal characters"
                )

    walk(raw, "")
    return failures


def _no_figures(raw: dict[str, Any]) -> list[str]:
    """Checklist item 9 — the pack contains no figures.

    Interface §6: "A pack describes *where a figure comes from and what it
    means*. The moment it contains the figure, it becomes exactly what spec §8
    exists to prevent: a fact stored as timeless, reused without re-checking."

    Only free-text fields are scanned.  ``published_precision`` is a typed
    numeric field describing the custodian's reporting precision rather than a
    value of the series, and flagging it would reject the one number a pack
    legitimately holds.
    """
    failures: list[str] = []

    def walk(node: Any, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("published_precision", "effective_date", "pack_version"):
                    continue
                walk(value, f"{trail}.{key}" if trail else key)
        elif isinstance(node, (list, tuple)):
            for i, value in enumerate(node):
                walk(value, f"{trail}[{i}]")
        elif isinstance(node, str):
            match = _FIGURE.search(node)
            if match:
                failures.append(
                    f"{trail} contains what looks like a statistic: {match.group(0)!r}. "
                    "A pack carrying a cached figure serves figures from memory (§6)"
                )

    walk(raw, "")
    return failures
