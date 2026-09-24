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

import html
from dataclasses import dataclass, field

from engine.elements import DerivedElement
from engine.render.figures import _NUMERAL, Payload, UnsourcedFigure
from engine.store.events import Retrieval
from engine.verdicts import ProposedVerdict, Verdict
from engine.verification.derive import render_as_implication
from engine.verification.sweep import FlipRow, SweepResult


#: What an empty ledger says when the claim never reached decomposition, as
#: opposed to one that was decomposed and lost nothing.
_NOT_DECOMPOSED = (
    "Not decomposed: no pack's vocabulary applies to this claim, so nothing was "
    "examined, kept or discarded. The verdict says why."
)


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
    #: False when the claim never reached decomposition: no pack resolved, or
    #: the pack has no lexicon for its language. The ledger is then empty
    #: because nothing was examined, not because nothing was removed, and
    #: "Nothing was discarded" beside "does not reconstruct" read as a whole
    #: claim dropped by a ledger claiming otherwise.
    decomposed: bool = True
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
        elif not self.decomposed:
            payload.line(f"  {_NOT_DECOMPOSED}")
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
            "decomposed": self.decomposed,
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

    def render_html(self) -> str:
        """The full artifact as an HTML fragment. There is no partial render here either.

        A web page is one more code path that emits the reconstruction, so
        AC-1 enumerates it like any other: it carries the ledger in the same
        payload, never behind a control. It is built beside :meth:`render`
        rather than on :meth:`to_dict` for two reasons. The reconstruction is a
        private field with no public accessor, and only this type may read it.
        And ``to_dict`` is never scanned for numerals, so a page built on it
        would be the one output path AC-7 did not reach.

        :meth:`render` runs first as the gate. It raises ``UnsourcedFigure``
        before any markup exists, so this method can emit only an artifact the
        text render has already accepted. What it adds is markup and fixed
        headings, and neither may carry a numeral: no counts ("four of ten
        flip"), no numbered citations. A count is computed, not retrieved,
        and §3 does not distinguish between the two. Citations are addressed
        by retrieval id, which appears in attributes and never in text.
        """
        self.render()

        e = html.escape
        out: list[str] = ['<article class="artifact">']

        if self.unconfirmed_marker:
            out.append(f'<p class="unconfirmed" role="status">{e(self.unconfirmed_marker)}</p>')

        out.append('<section class="claim"><h2>Original claim</h2>')
        out.append(f"<blockquote>{e(self.claim_text)}</blockquote></section>")

        # §7.1 — one section holds both. A reader cannot scroll to the
        # reconstruction without passing through the frame that carries the
        # ledger, and no control hides either.
        out.append('<section class="reconstruction-and-ledger">')
        out.append("<h2>Reconstructed</h2>")
        if self.does_reconstruct:
            anchor = self.citations[-1].id if self.citations else None
            if anchor is None:
                out.append(f'<p class="reconstruction">{e(self._reconstruction)}</p>')
            else:
                out.append(
                    f'<p class="reconstruction" data-retrieval-id="{e(str(anchor))}">'
                    f'{e(self._reconstruction)} '
                    f'<a href="#retrieval-{e(str(anchor))}">source</a></p>'
                )
        else:
            out.append('<p class="reconstruction">does not reconstruct</p>')
            out.append(
                "<p>The surviving elements do not compose into a coherent statement.</p>"
            )
        out.append('<h3 class="ledger-heading">Discard ledger</h3>')
        if self.ledger:
            out.append('<ul class="ledger">')
            for entry in self.ledger:
                out.append(
                    f'<li><span class="fragment">{e(entry.fragment)}</span> '
                    f'<span class="status">{e(entry.status)}</span>'
                    f'<p class="reason">{e(entry.reason)}</p></li>'
                )
            out.append("</ul>")
        elif not self.decomposed:
            out.append(f'<p class="ledger">{e(_NOT_DECOMPOSED)}</p>')
        else:
            out.append('<p class="ledger">Nothing was discarded.</p>')
        out.append("</section>")

        # §7.5 — one container for every label. The label is the only thing
        # that varies; there is no per-label class, so no stylesheet can give
        # Insufficient Data the error styling AC-5 forbids.
        out.append('<section class="verdict"><h2>Verdict</h2>')
        out.append(f'<p class="verdict-label">{e(_label(self.verdict.label))}</p>')
        out.append(f'<p class="verdict-rationale">{e(self.verdict.rationale)}</p>')
        if self.verdict.capped:
            out.append(f'<p class="verdict-cap">Capped: {e(self.verdict.cap_reason)}</p>')
        out.append("</section>")

        out.append('<section class="sweep"><h2>Robustness sweep</h2>')
        if not self.sweep.ran:
            out.append("<p>Could not run.</p>")
            out.append(f"<p>{e(self.sweep.reason_not_run)}</p>")
            out.append("<p>The verdict is capped accordingly; silence is not a pass.</p>")
        else:
            out.append('<table class="flip-table"><thead><tr><th scope="col">Result</th>'
                       '<th scope="col">Alternative</th><th scope="col">What was compared</th>'
                       "</tr></thead><tbody>")
            for row in self.sweep.rows:
                result = "holds" if row.conclusion_holds else "flips"
                out.append(
                    f'<tr class="{result}" data-retrieval-id="{e(str(row.computed_from_retrieval_id))}">'
                    f"<td>{result}</td>"
                    f"<td>{e(row.test.value)}: {e(row.alternative)}</td>"
                    f"<td>{e(row.detail)}</td></tr>"
                )
            out.append("</tbody></table>")
        out.append("</section>")

        out.append('<section class="citations"><h2>Citations</h2>')
        if not self.citations:
            out.append("<p>No retrieval was performed.</p>")
        else:
            # A measure's framing caveat usually applies to every figure in its
            # series, and repeating it under each one buried the citations: a
            # year of monthly figures printed the same paragraph twelve times.
            # So consecutive citations sharing a caveat are grouped and the
            # caveat is stated once, before them. Nothing is dropped: a caveat
            # that changes starts a new group, and every citation keeps its
            # own entry. The text render still repeats it per citation.
            groups: list[tuple[str | None, list[Retrieval]]] = []
            for retrieval in self.citations:
                if groups and groups[-1][0] == retrieval.caveat:
                    groups[-1][1].append(retrieval)
                else:
                    groups.append((retrieval.caveat, [retrieval]))
            for caveat, members in groups:
                if caveat:
                    out.append(
                        f'<p class="caveat">caveat on the citations that follow: {e(caveat)}</p>'
                    )
                out.append('<ul class="citation-list">')
                for retrieval in members:
                    rid = e(str(retrieval.id))
                    out.append(
                        f'<li id="retrieval-{rid}">'
                        f'<span class="series">{e(retrieval.custodian_id)} / {e(retrieval.series_id)}</span> '
                        f'<span class="figure">{e(str(retrieval.value))} {e(retrieval.unit)}</span> '
                        f'<span class="period">for {e(retrieval.reference_period)}</span>'
                        f'<p class="provenance">revision {e(retrieval.revision_status.value)}; '
                        f"retrieved {e(retrieval.retrieved_at.isoformat())}; "
                        f"continuity {e(retrieval.continuity_status)}</p></li>"
                    )
                out.append("</ul>")
        out.append("</section>")

        out.append('<section class="routing"><h2>Routing</h2>')
        if not self.routing:
            out.append("<p>No route was established.</p>")
        else:
            for note in self.routing:
                out.append(f'<p class="route">{e(note.measure)} → {e(note.custodian)}</p>')
                out.append(f"<p>{e(note.rationale)}</p>")
                for alternative in note.alternatives_considered:
                    out.append(f'<p class="considered">considered: {e(alternative)}</p>')
        out.append("</section>")

        if self.derived:
            out.append('<section class="derived"><h2>Derived elements (proposed, not confirmed)</h2>')
            for element in self.derived:
                out.append(
                    f'<div class="derived-element"><span class="tag">{e(element.tag.value)}</span>'
                    f"<p>{e(render_as_implication(element))}</p>"
                    f'<p class="operation">operation: {e(element.operation.value)}</p></div>'
                )
            out.append("</section>")

        out.append("</article>")
        return "\n".join(out)

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
