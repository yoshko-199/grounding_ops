"""AC-7 — No unsourced figure.

Constraint: spec §3.  Every figure originates from a recorded retrieval.

"For every numeric literal in every output [...] assert it resolves to a
``retrievals.id``. [...] **This must fail the render, not warn.**"

Warning was never an option. An unsourced figure that renders with a warning
still renders, and the artifact still carries custodian names and a citation
trail around it; the warning goes to a log nobody reads and the number goes to
a reader who assumes it was checked.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.figures import Figure
from engine.ids import RetrievalId
from engine.pipeline import verify
from engine.render.figures import (
    NotQuotedFromClaim,
    Payload,
    UnsourcedFigure,
    scan_prose,
)

CLAIM = "prices rose over the last three years due to governmental incompetence"


def test_a_numeral_in_prose_fails_the_render() -> None:
    payload = Payload(claim_text="")
    payload.text("inflation reached 4.2 percent")
    with pytest.raises(UnsourcedFigure, match="4.2"):
        payload.render()


def test_it_raises_rather_than_warning() -> None:
    """The criterion says fail, not warn."""
    import warnings

    payload = Payload(claim_text="")
    payload.text("the figure was 17")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(UnsourcedFigure):
            payload.render()


def test_a_sourced_figure_passes_and_carries_its_reference_period() -> None:
    """§5 requires the reference period to render alongside the figure."""
    payload = Payload(claim_text="")
    payload.figure(
        Figure(Decimal("102.4"), "index_points", RetrievalId("r-1"), "2021-12")
    )
    rendered = payload.render()
    assert "102.4" in rendered
    assert "2021-12" in rendered
    assert payload.retrieval_ids() == ("r-1",)


def test_a_figure_cannot_be_built_without_a_retrieval() -> None:
    """Making the invalid state unrepresentable is AC-7 moved earlier."""
    with pytest.raises(TypeError):
        Figure(Decimal("1.0"), "index_points")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="reference_period"):
        Figure(Decimal("1.0"), "index_points", RetrievalId("r"), "")


def test_a_float_figure_is_rejected() -> None:
    """Float arithmetic would make §9.2's bands depend on representation error."""
    with pytest.raises(TypeError, match="Decimal"):
        Figure(1.0, "index_points", RetrievalId("r"), "2021-12")  # type: ignore[arg-type]


# -- the quoted channel, and its limits -------------------------------------


def test_the_claim_under_examination_may_be_quoted() -> None:
    payload = Payload(claim_text="prices rose 4.2 percent in 2021")
    payload.quoted("prices rose 4.2 percent in 2021")
    assert "4.2" in payload.render()


def test_the_quoted_channel_rejects_anything_not_in_the_claim() -> None:
    """The one bypass is narrow, and the narrowness is enforced.

    Without this the channel would be a general-purpose route for unsourced
    numbers wearing the name of a quotation.
    """
    payload = Payload(claim_text="prices rose in 2021")
    with pytest.raises(NotQuotedFromClaim):
        payload.quoted("inflation reached 9.9 percent")


def test_quoted_text_never_enters_the_citation_trail() -> None:
    """Nothing was retrieved, so nothing may appear as a retrieval."""
    payload = Payload(claim_text="prices rose 4.2 percent")
    payload.quoted("prices rose 4.2 percent")
    assert payload.retrieval_ids() == ()


# -- the whole artifact -----------------------------------------------------


def test_every_numeral_in_a_rendered_artifact_is_accounted_for(
    registry, context, adapters, store
) -> None:
    """The end-to-end assertion: the render either resolves every numeral or raises."""
    artifact = verify(CLAIM, context, registry, adapters, store).artifact
    rendered = artifact.render()
    assert rendered
    assert artifact.citations
    # Every citation's figure appears, each beside its reference period.
    for retrieval in artifact.citations:
        assert str(retrieval.value) in rendered
        assert retrieval.reference_period in rendered


def test_a_reconstruction_carrying_an_unmatched_numeral_fails_the_render(
    registry, context, adapters, store
) -> None:
    """Negative test of the reconstruction check specifically."""
    from dataclasses import replace

    artifact = verify(CLAIM, context, registry, adapters, store).artifact
    tampered = replace(artifact, _reconstruction="Prices rose 999.9 index_points.")
    with pytest.raises(UnsourcedFigure, match="999.9"):
        tampered.render()


def test_flip_table_cells_cite_their_retrieval(registry, context, adapters, store) -> None:
    """AC-7's extended surface: sweeps.computed_from_retrieval_id non-null."""
    artifact = verify(CLAIM, context, registry, adapters, store).artifact
    assert artifact.sweep.rows
    for row in artifact.sweep.rows:
        assert row.computed_from_retrieval_id is not None


def test_pack_contents_carry_no_numeric_literals(pack) -> None:
    """AC-7's third extended surface, checked at load and asserted here."""
    for measure in pack.measures:
        assert not scan_prose(measure.definition)
        for confusion in measure.known_confusions:
            assert not scan_prose(confusion)
    for custodian in pack.custodians:
        assert not scan_prose(custodian.mandate)
        assert not scan_prose(custodian.integrity_annotation)


# ---------------------------------------------------------------------------
# The derived-element channel.
#
# Found by running a real claim from a political-claim aggregator: a figure
# and a connective in one sentence — "corporate tax ... 25 percent ...
# therefore ..." — crashed the render. The numeral was the claimant's own,
# quoted verbatim into a derived element by §9.7's construction, but it
# reached output through the prose channel and AC-7 correctly refused it.
#
# Failing closed was right. Failing on the claimant's own numbers was still a
# defect, and it covered a large fraction of the claims anyone would check.
# ---------------------------------------------------------------------------

NUMERIC_INFERENCE = (
    "corporate tax rose to 25 percent over the last four years "
    "therefore the promise was broken"
)


def test_a_claim_carrying_a_figure_and_a_connective_renders(
    registry, context, adapters, store
) -> None:
    """The regression. Before the derived channel existed this raised."""
    artifact = verify(NUMERIC_INFERENCE, context, registry, adapters, store).artifact
    output = artifact.render()
    assert "DERIVED ELEMENTS" in output
    assert "25 percent" in output


def test_the_derived_channel_still_refuses_an_invented_numeral() -> None:
    """The negative control, and the reason the channel is not just `quoted`.

    A channel that has never been seen to reject anything is a channel nobody
    has confirmed is checking. The invariant is not "derived text is exempt";
    it is "no numeral appears that the claim did not contain".
    """
    payload = Payload(claim_text="corporate tax rose therefore the promise was broken")
    with pytest.raises(UnsourcedFigure, match="42"):
        payload.derived("the promise was broken is asserted to follow from 42 percent")


def test_the_derived_channel_admits_only_the_claim_s_own_numerals() -> None:
    """A numeral the claim does contain passes; a neighbour of it does not."""
    payload = Payload(claim_text="tax was 25 percent therefore the promise was broken")
    payload.derived("the promise was broken is asserted to follow from tax was 25")
    with pytest.raises(UnsourcedFigure, match="26"):
        payload.derived("the promise was broken is asserted to follow from tax was 26")


def test_a_derived_element_never_enters_the_citation_trail() -> None:
    """§9.7.4 — derived elements carry no retrieval, so none may be implied.

    The channel needs a marker to be exempt from the numeral scan, and a
    marker that leaked into `retrieval_ids()` would put a citation-shaped
    token next to text that was never retrieved.
    """
    payload = Payload(claim_text="tax was 25 percent therefore the promise was broken")
    payload.quoted("tax was 25 percent")
    payload.derived("the promise was broken is asserted to follow from tax was 25")
    assert payload.retrieval_ids() == ()


def test_the_derived_channel_is_not_a_general_bypass(
    registry, context, adapters, store
) -> None:
    """Prose is still prose. The new channel must not have widened `text`."""
    payload = Payload(claim_text="tax was 25 percent")
    payload.text("the government raised it to 30 percent")
    with pytest.raises(UnsourcedFigure, match="30"):
        payload.render()
