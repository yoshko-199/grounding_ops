"""Negative tests for the interface §6 validation checklist.

A validator whose checks never fire is indistinguishable from one with no
checks at all, and both look identical when the only pack in the tree is
valid.  Every check below is exercised by breaking exactly one thing in the
fixture pack and asserting the corresponding failure appears.

This mirrors how ``scripts/check_spec.py`` was established: the checks were
negative-tested by injecting faults, because a green run proves nothing about
a check that cannot fail.
"""

from __future__ import annotations

import pathlib

import pytest

from engine.packs.loader import PackInvalid, load, validate

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture" / "zz.toml"


def _mutated(tmp_path: pathlib.Path, old: str, new: str) -> pathlib.Path:
    text = FIXTURE.read_text(encoding="utf-8")
    assert old in text, f"fixture no longer contains {old!r}; update this test"
    path = tmp_path / "broken.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return path


def _failures(tmp_path: pathlib.Path, old: str, new: str) -> str:
    return "\n".join(validate(_mutated(tmp_path, old, new)).failures)


def test_the_fixture_pack_admits() -> None:
    """The control. Every negative test below is meaningless without it."""
    report = validate(FIXTURE)
    assert report.admitted, "\n".join(report.failures)


def test_pack_loads_into_a_usable_structure() -> None:
    pack = load(FIXTURE)
    assert str(pack.jurisdiction) == "ZZ"
    assert pack.version == "1.0.0-fixture"
    assert pack.measure("price_index") is not None
    assert pack.custodian("zzstat") is not None
    assert pack.route_for("price_index") is not None
    assert pack.measure("no_such_measure") is None


# -- item 1: all five required blocks ---------------------------------------


def test_missing_lexicons_block_is_rejected(tmp_path: pathlib.Path) -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    truncated = text[: text.index("[[lexicons]]")]
    path = tmp_path / "no_lexicons.toml"
    path.write_text(truncated, encoding="utf-8")
    assert "required block missing or empty: [lexicons]" in "\n".join(
        validate(path).failures
    )


# -- item 2: custodian completeness -----------------------------------------


def test_empty_integrity_annotation_is_rejected(tmp_path: pathlib.Path) -> None:
    """Interface §3.2 requires `none known` to be written explicitly.

    The field is required so that its absence is a deliberate statement
    rather than an oversight.
    """
    failures = _failures(
        tmp_path,
        'integrity_annotation = "none known"',
        'integrity_annotation = ""',
    )
    assert "integrity_annotation is required" in failures


# -- item 3 and 7: everything resolves to a declared custodian --------------


def test_measure_pointing_at_undeclared_custodian_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    failures = _failures(
        tmp_path,
        'custodian_id = "zzstat"\nseries_identifier = "ZZ-PRICE"',
        'custodian_id = "some_news_outlet"\nseries_identifier = "ZZ-PRICE"',
    )
    assert "undeclared custodian 'some_news_outlet'" in failures


def test_routing_rule_pointing_outside_declared_custodians_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    """The mechanical form of "no generic fallback" (AC-14).

    A route to something that is not a custodian of record is precisely the
    dilution interface §4.1 exists to prevent.
    """
    failures = _failures(
        tmp_path,
        'measure_id = "price_index"\ncustodian_id = "zzstat"',
        'measure_id = "price_index"\ncustodian_id = "a_search_engine"',
    )
    assert "is not a declared custodian" in failures


def test_measure_with_no_routing_rule_is_rejected(tmp_path: pathlib.Path) -> None:
    failures = _failures(
        tmp_path,
        '[[routing_rules]]\nmeasure_id = "sparse_gauge"',
        '[[routing_rules]]\nmeasure_id = "sparse_gauge_typo"',
    )
    assert "measure 'sparse_gauge' has no routing rule" in failures


# -- item 5 and AC-4: alternatives_considered -------------------------------


def test_empty_alternatives_without_declaration_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    """AC-4 admits emptiness only where the pack declares no alternative exists.

    A routing table showing only winners is indistinguishable from one built
    backwards from preferred answers.
    """
    failures = _failures(
        tmp_path,
        'rationale = "Sole compiler of the fixture price index."\nno_alternative_custodian = true',
        'rationale = "Sole compiler of the fixture price index."',
    )
    assert "alternatives_considered[] is empty without no_alternative_custodian" in failures


def test_declaring_no_alternatives_while_listing_them_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    failures = _failures(
        tmp_path,
        'rationale = "Sole compiler of the fixture output index."\nno_alternative_custodian = true',
        'rationale = "Sole compiler of the fixture output index."\n'
        'no_alternative_custodian = true\nalternatives_considered = ["something"]',
    )
    assert "declares no_alternative_custodian while also listing alternatives" in failures


# -- item 6: break register -------------------------------------------------


def test_break_without_custodian_notice_is_rejected(tmp_path: pathlib.Path) -> None:
    """§9.5 — a break the engine inferred is a suspicion, not a register entry."""
    failures = _failures(
        tmp_path,
        'custodian_notice_ref = "ZZ Statistical Office, Fixture Notice on Rebasing"',
        'custodian_notice_ref = ""',
    )
    assert "cites no custodian_notice_ref" in failures


def test_linked_series_without_identifier_is_rejected(tmp_path: pathlib.Path) -> None:
    failures = _failures(
        tmp_path,
        '  linked_series_available = true\n  linked_series_identifier = "ZZ-PRICE-LINKED"',
        "  linked_series_available = true",
    )
    assert "names no linked_series_identifier" in failures


# -- item 4: measure completeness -------------------------------------------


def test_empty_known_confusions_is_rejected(tmp_path: pathlib.Path) -> None:
    failures = _failures(tmp_path, 'known_confusions = ["none known"]', "known_confusions = []")
    assert "known_confusions[] may not be empty" in failures


def test_missing_admissible_source_ref_is_rejected(tmp_path: pathlib.Path) -> None:
    """Interface v1.1. Without it, checklist item 8 cannot be checked at all."""
    failures = _failures(
        tmp_path,
        'admissible_source_ref = "ZZ Electoral Commission, Fixture Certification Record"',
        'admissible_source_ref = ""',
    )
    assert "admissible_source_ref is required" in failures


# -- items 10 and 11: lexicons ----------------------------------------------


def test_lexicon_missing_a_derivation_operation_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    """All five operations must be keyed, even where the list is empty.

    An operation silently absent from a lexicon under-fires invisibly: the
    output looks identical to a claim that simply had no such implication.
    """
    failures = _failures(
        tmp_path,
        '"scope-discharge" = ["all", "every", "always", "never", "nobody", "everyone", "none"]',
        "",
    )
    assert "derivation_triggers is missing 'scope-discharge'" in failures


def test_empty_forbidden_connectives_is_rejected(tmp_path: pathlib.Path) -> None:
    """This is where AC-15's "equivalents in each pack's declared languages" live."""
    text = FIXTURE.read_text(encoding="utf-8")
    start = text.index("forbidden_connectives = [")
    end = text.index("]", start) + 1
    path = tmp_path / "no_forbidden.toml"
    path.write_text(text[:start] + "forbidden_connectives = []" + text[end:], encoding="utf-8")
    assert "forbidden_connectives may not be empty" in "\n".join(validate(path).failures)


def test_causal_connective_in_composition_list_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    """§9.9.2 — the allowlist admits enumeration and sequencing only.

    This is the check that stops a pack from handing the reconstructor the
    vocabulary for a sentence §9.6 forbids it to write.
    """
    failures = _failures(
        tmp_path,
        'composition_connectives = ["and", ", ", "; ", "then"]',
        'composition_connectives = ["and", ", ", "because"]',
    )
    assert "§9.9.2 admits enumeration and sequencing only" in failures


def test_language_declared_without_lexicon_is_rejected(tmp_path: pathlib.Path) -> None:
    failures = _failures(tmp_path, 'languages = ["en"]', 'languages = ["en", "he"]')
    assert "declared in the header with no lexicon entry" in failures


def test_lexicon_for_undeclared_language_is_rejected(tmp_path: pathlib.Path) -> None:
    failures = _failures(tmp_path, '[[lexicons]]\nlanguage = "en"', '[[lexicons]]\nlanguage = "fr"')
    assert "absent from header.languages" in failures


# -- item 9: the pack contains no figures -----------------------------------


def test_a_figure_in_a_free_text_field_is_rejected(tmp_path: pathlib.Path) -> None:
    """Interface §6's sharpest item.

    A pack carrying a cached statistic becomes exactly what spec §8 exists to
    prevent: a fact stored as timeless, reused without re-checking.
    """
    failures = _failures(
        tmp_path,
        '"Manufacturing output is not total output.",',
        '"Manufacturing output rose 4.2% over the period.",',
    )
    assert "looks like a statistic" in failures


def test_published_precision_is_not_mistaken_for_a_figure() -> None:
    """The one number a pack legitimately holds.

    ``published_precision`` describes the custodian's reporting precision and
    drives §9.2's bands. Scanning it would reject every valid pack, which is
    how a no-figures check gets quietly disabled.
    """
    report = validate(FIXTURE)
    assert report.admitted
    assert load(FIXTURE).measure("price_index").published_precision == 0.1


# -- loading behaviour ------------------------------------------------------


def test_invalid_pack_raises_rather_than_loading_partially(
    tmp_path: pathlib.Path,
) -> None:
    """Interface §3: a partial pack routes some claims and silently drops others."""
    path = _mutated(tmp_path, 'integrity_annotation = "none known"', 'integrity_annotation = ""')
    with pytest.raises(PackInvalid) as exc:
        load(path)
    assert exc.value.failures


# ---------------------------------------------------------------------------
# Markup.
#
# Pack prose is copied verbatim into plain-text artifacts — a measure's first
# known confusion becomes the framing caveat on every citation line for that
# measure. Emphasis markers therefore reach the reader as literal characters
# beside a custodian's name.
#
# Found by review after the euro and sterling measures shipped with
# "**Cross-derived, not sampled.**" as their first confusion.
# ---------------------------------------------------------------------------


def test_bold_markup_in_a_confusion_does_not_load(tmp_path: pathlib.Path) -> None:
    failures = _failures(
        tmp_path,
        "Month-over-month change against year-over-year change.",
        "**Month-over-month** change against year-over-year change.",
    )
    assert "contains markup" in failures
    assert "'**'" in failures


def test_backticks_in_a_definition_do_not_load(tmp_path: pathlib.Path) -> None:
    failures = _failures(
        tmp_path,
        "Index of consumer prices against a fixed basket and base year.",
        "Index of `consumer prices` against a fixed basket and base year.",
    )
    assert "contains markup" in failures


def test_an_html_tag_in_a_mandate_does_not_load(tmp_path: pathlib.Path) -> None:
    failures = _failures(
        tmp_path,
        "Fixture national statistical office",
        "Fixture <b>national</b> statistical office",
    )
    assert "contains markup" in failures


def test_the_markup_check_does_not_fire_on_ordinary_prose(
    tmp_path: pathlib.Path,
) -> None:
    """The control that keeps the guard from being a nuisance.

    A single asterisk, an inequality, and an em dash are ordinary punctuation
    in a custodian's own wording. Rejecting them would push pack authors toward
    paraphrasing the source, which is the opposite of the point.
    """
    failures = _failures(
        tmp_path,
        "Month-over-month change against year-over-year change.",
        "Month-over-month change* against year-over-year change — see <0 cases.",
    )
    assert "contains markup" not in failures


def test_the_admitted_live_pack_carries_no_markup() -> None:
    """The regression: this pack shipped with bold in it."""
    live = pathlib.Path(__file__).resolve().parents[2] / "packs" / "live" / "il.toml"
    if not live.exists():
        pytest.skip("no live pack")
    report = validate(live)
    assert report.admitted, "\n".join(report.failures)


# -- interface v1.3: lexicon-declared jurisdiction names --------------------


def test_pack_loads_the_declared_names() -> None:
    """The fixture declares one for exactly this coverage."""
    pack = load(FIXTURE)
    lexicon = pack.lexicon(pack.header.languages[0])
    assert lexicon is not None
    assert lexicon.names == ("Zeeland",)


def test_names_defaults_to_empty_when_absent(tmp_path: pathlib.Path) -> None:
    """Optional, and absence is not a validation failure — §9.8.2 rule 1
    simply gets nothing to match beyond the code, which is the pre-v1.3
    behaviour exactly."""
    path = _mutated(tmp_path, 'names = ["Zeeland"]\n', "")
    report = validate(path)
    assert report.admitted, "\n".join(report.failures)
    pack = load(path)
    lexicon = pack.lexicon(pack.header.languages[0])
    assert lexicon is not None
    assert lexicon.names == ()


# -- interface v1.4: surface_vocabulary (rise/fall/prediction) --------------


def test_pack_loads_the_surface_vocabulary() -> None:
    from engine.packs.schema import SurfaceCategory

    pack = load(FIXTURE)
    lexicon = pack.lexicon(pack.header.languages[0])
    assert lexicon is not None
    assert "rose" in lexicon.surface_vocabulary[SurfaceCategory.RISE]
    assert "fell" in lexicon.surface_vocabulary[SurfaceCategory.FALL]
    assert "projected" in lexicon.surface_vocabulary[SurfaceCategory.PREDICTION]


def test_surface_vocabulary_missing_a_category_is_rejected(tmp_path: pathlib.Path) -> None:
    """Required, on the same footing as derivation_triggers: all three
    categories must be keyed, an empty list only where declared explicitly."""
    failures = _failures(tmp_path, "prediction = [", "removed_prediction_key = [")
    assert "surface_vocabulary" in failures
    assert "prediction" in failures


def test_missing_surface_vocabulary_block_entirely_is_rejected(tmp_path: pathlib.Path) -> None:
    path = _mutated(tmp_path, "[lexicons.surface_vocabulary]", "[lexicons.renamed_block]")
    report = validate(path)
    assert not report.admitted
    failures = "\n".join(report.failures)
    assert "surface_vocabulary" in failures
