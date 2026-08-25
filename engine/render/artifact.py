"""The output artifact — reconstruction and ledger, inseparable.

Spec §7.1: "The reconstructed claim never renders, exports, or copies without
its discard ledger. If it can be detached, the tool is a laundering device."

AC-1 tests this by enumerating "every code path that emits reconstructed
claim text — UI render, API response, export format, clipboard payload, print
view, log line, error message, notification body" and asserting the ledger
travels with each.  The approach here is to make that enumeration short: the
reconstruction text is a private field with no public accessor, and the only
ways out of this type emit both.

Note the deliberate omissions, which are AC-2:  no ``to_tweet``, no
``summary``, no ``max_length``, no truncation, no platform template.  §7.2's
reasoning is that "the moment output is optimised for distribution, users
will run verifications selectively until one produces the answer they
wanted."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.elements import DerivedElement
from engine.render.figures import _NUMERAL, Payload, UnsourcedFigure
from engine.store.events import Retrieval
from engine.verdicts import ProposedVerdict, Verdict
from engine.verification.derive import render_as_implication
from engine.verification.sweep import FlipRow, SweepResult


@dataclass(frozen=True, slots=True)
class DiscardEntry:
    """One row of the discard ledger: what was removed, and why."""

    fragment: str
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class RoutingNote:
    """§7.4 — why this custodian and not another, carried into output."""

    measure: str
    custodian: str
    rationale: str
    alternatives_considered: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Artifact:
    """Everything a verification emits, as one indivisible payload."""

    claim_text: str
    _reconstruction: str
    does_reconstruct: bool
    element_set_hash: str
    ledger: tuple[DiscardEntry, ...]
    verdict: ProposedVerdict
    sweep: SweepResult
    citations: tuple[Retrieval, ...] = ()
    routing: tuple[RoutingNote, ...] = ()
    derived: tuple[DerivedElement, ...] = ()
    unconfirmed_marker: str = ""
    _lines: tuple[str, ...] = field(default=(), compare=False)

    # -- the only ways out --------------------------------------------------

    def render(self) -> str:
        """The full artifact as text. There is no partial render."""
        payload = Payload(claim_text=self.claim_text)

        if self.unconfirmed_marker:
            payload.line(f"[{self.unconfirmed_marker}]").line()

        payload.line("ORIGINAL CLAIM").text("  ")
        payload.quoted(self.claim_text).line().line()

        payload.line("RECONSTRUCTED")
        if self.does_reconstruct:
            self._render_reconstruction(payload)
        else:
            payload.line("  does not reconstruct")
            payload.line(
                "  The surviving elements do not compose into a coherent statement."
            )
        payload.line()

        # §7.1 — the ledger is in the same payload, not behind a control, a
        # second request, or a pagination boundary.
        payload.line("DISCARD LEDGER")
        if self.ledger:
            for entry in self.ledger:
                payload.text("  - ")
                payload.quoted(entry.fragment)
                payload.line(f" [{entry.status}]")
                payload.line(f"      {entry.reason}")
        else:
            payload.line("  Nothing was discarded.")
        payload.line()

        payload.line("VERDICT")
        payload.line(f"  {_label(self.verdict.label)}")
        payload.line(f"  {self.verdict.rationale}")
        if self.verdict.capped:
            payload.line(f"  Capped: {self.verdict.cap_reason}")
        payload.line()

        self._render_flip_table(payload)
        self._render_citations(payload)
        self._render_routing(payload)
        self._render_derived(payload)

        return payload.render()

    def to_dict(self) -> dict[str, object]:
        """Structured form. Carries the ledger for the same reason render does."""
        return {
            "claim": self.claim_text,
            "reconstruction": self._reconstruction if self.does_reconstruct else None,
            "does_reconstruct": self.does_reconstruct,
            "element_set_hash": self.element_set_hash,
            "discard_ledger": [
                {"fragment": e.fragment, "status": e.status, "reason": e.reason}
                for e in self.ledger
            ],
            "verdict": {
                "label": self.verdict.label.value,
                "rationale": self.verdict.rationale,
                "state": self.verdict.state.value,
                "capped": self.verdict.capped,
            },
            "flip_table": [
                {
                    "test": row.test.value,
                    "alternative": row.alternative,
                    "conclusion_holds": row.conclusion_holds,
                    "computed_from_retrieval_id": str(row.computed_from_retrieval_id),
                }
                for row in self.sweep.rows
            ],
            "sweep_ran": self.sweep.ran,
            "citations": [
                {
                    "retrieval_id": str(r.id),
                    "custodian": r.custodian_id,
                    "series": r.series_id,
                    "reference_period": r.reference_period,
                    "revision_status": r.revision_status.value,
                }
                for r in self.citations
            ],
            "derived_elements": [
                {
                    "text": render_as_implication(d),
                    "operation": d.operation.value,
                    "tag": d.tag.value,
                    "state": d.state.value,
                }
                for d in self.derived
            ],
            "unconfirmed": bool(self.unconfirmed_marker),
        }

    def __str__(self) -> str:
        return self.render()

    # -- sections -----------------------------------------------------------

    def _render_reconstruction(self, payload: Payload) -> None:
        """Emit the reconstruction, with every numeral in it tied to a retrieval.

        The reconstruction is composed by §9.9's grammar from element surface
        forms and published figures, so any numeral it carries must appear in
        a citation. Checking that here rather than trusting the reconstructor
        keeps AC-7 enforced at the boundary where output actually happens,
        which is where the criterion places it.
        """
        sourced = {
            numeral
            for retrieval in self.citations
            for numeral in _numerals_in(retrieval)
        }
        unaccounted = [
            token for token in _NUMERAL.findall(self._reconstruction)
            if token not in sourced
        ]
        if unaccounted:
            raise UnsourcedFigure(
                f"the reconstruction carries {sorted(set(unaccounted))} with no "
                "matching retrieval. A figure in a reconstruction must originate "
                "from the same recorded retrieval as any other figure (§3)"
            )
        anchor = self.citations[-1].id if self.citations else None
        if anchor is None:
            payload.line(f"  {self._reconstruction}")
        else:
            payload.sourced(f"  {self._reconstruction}\n", anchor)


    def _render_flip_table(self, payload: Payload) -> None:
        """§9.3 — rendered with the verdict, never omitted from a Misleading one."""
        payload.line("ROBUSTNESS SWEEP")
        if not self.sweep.ran:
            payload.line("  Could not run.")
            payload.line(f"  {self.sweep.reason_not_run}")
            payload.line("  The verdict is capped accordingly; silence is not a pass.")
            payload.line()
            return
        for row in self.sweep.rows:
            verdict = "holds" if row.conclusion_holds else "FLIPS"
            payload.sourced(
                f"  [{verdict}] {row.test.value}: {row.alternative}\n"
                f"      {row.detail}\n",
                row.computed_from_retrieval_id,
            )
        payload.line()

    def _render_citations(self, payload: Payload) -> None:
        """§5 — the citation record, all six fields plus continuity."""
        payload.line("CITATIONS")
        if not self.citations:
            payload.line("  No retrieval was performed.")
            payload.line()
            return
        for retrieval in self.citations:
            payload.sourced(
                f"  {retrieval.custodian_id} / {retrieval.series_id}\n"
                f"      figure {retrieval.value} {retrieval.unit}"
                f" for {retrieval.reference_period}\n"
                f"      revision {retrieval.revision_status.value};"
                f" retrieved {retrieval.retrieved_at.isoformat()};"
                f" continuity {retrieval.continuity_status}\n",
                retrieval.id,
            )
            if retrieval.caveat:
                payload.sourced(f"      caveat: {retrieval.caveat}\n", retrieval.id)
        payload.line()

    def _render_routing(self, payload: Payload) -> None:
        """§7.4 — the alternatives are the audit."""
        payload.line("ROUTING")
        if not self.routing:
            payload.line("  No route was established.")
            payload.line()
            return
        for note in self.routing:
            payload.line(f"  {note.measure} -> {note.custodian}")
            payload.line(f"      {note.rationale}")
            for alternative in note.alternatives_considered:
                payload.line(f"      considered: {alternative}")
        payload.line()

    def _render_derived(self, payload: Payload) -> None:
        """§9.7.5 — as implication, never as quotation."""
        if not self.derived:
            return
        payload.line("DERIVED ELEMENTS (proposed, not confirmed)")
        for element in self.derived:
            # The tag and the operation are prose the system chose; the
            # implication is the claimant's own words plus a closed scaffold.
            # They go through different channels because AC-7 asks different
            # questions of them — a numeral in the first would be invented, a
            # numeral in the second was quoted.
            payload.text(f"  [{element.tag.value}] ")
            payload.derived(render_as_implication(element))
            payload.line()
            payload.line(f"      operation: {element.operation.value}")
        payload.line()


def _numerals_in(retrieval: Retrieval) -> set[str]:
    """Every numeral this retrieval justifies."""
    return set(_NUMERAL.findall(f"{retrieval.value} {retrieval.reference_period}"))


def _label(verdict: Verdict) -> str:
    """§7.5 — Insufficient Data renders identically to any other verdict.

    Same container, same position, same typographic weight. No warning glyph,
    no error styling, and nothing implying it is a result to be resolved
    rather than an answer.
    """
    return verdict.value.replace("_", " ").upper()
