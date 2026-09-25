"""The bottom line — the verdict in plain words, above the full record.

The artifact below it is written for a reader who wants to audit the result:
a ledger of reasons, a flip table, a citation trail. This section is written
for a reader who wants the answer, and says in ordinary sentences what the
record supports, what it contradicts, what no record could settle, the
closest version of the claim the sources back, and where the figures came
from. It follows the working order of an empirical check:

1. isolate the checkable assertion from opinion and rhetoric
   (*True*, *False*, *Not checked* against *Not checkable*);
2. state what evidence would settle it and go to the primary source for it
   (the published figure beside each fragment, and *Sources*);
3. look for disconfirming evidence (*Tested against other readings*: the
   robustness sweep, restated);
4. give a verdict calibrated to the strength of that evidence, and say it is
   provisional (*Verdict*, *Open to correction*).

Three constraints shaped it, and each is the reason for something that might
otherwise look like an omission.

**It is not detachable (§7.1).** It carries the closest verified version of
the claim, which is the reconstruction, so it also carries every element the
ledger removes, each with what happened to it. Lifted out on its own it still
says what was dropped. It has no public accessor on the artifact and is only
ever emitted inside a full render.

**It is not a distribution format (§7.2).** No length budget, no character
target, no truncation: it grows with the claim, one line per element, and is
never emitted by itself. It is the same record in plainer words, not a
shorter record.

**It carries no unsourced numeral (§3, AC-7).** Every figure in it goes
through the retrieval it came from; the claimant's own words go through the
quoted channel; counts are never stated. The reconstruction is checked here
exactly as the full render checks it, so this section cannot be the one path
where an unsourced figure gets through.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from engine.ids import RetrievalId
from engine.render.figures import _NUMERAL, Payload, UnsourcedFigure

HEADING = "Bottom line"
LEAD = "In plain words. The full record, with every reason and figure, follows."


@dataclass(frozen=True, slots=True)
class Finding:
    """One element as the bottom line states it."""

    fragment: str
    kind: str
    status: str
    band: str | None = None


@dataclass(frozen=True, slots=True)
class Source:
    """One cited figure, as the bottom line needs it."""

    retrieval_id: RetrievalId
    custodian_id: str
    series_id: str
    value: str
    unit: str
    reference_period: str
    revision_status: str
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class Flip:
    """A sweep alternative under which the conclusion did not hold."""

    test: str
    alternative: str
    retrieval_id: RetrievalId


@dataclass(frozen=True, slots=True)
class Basis:
    """Everything the bottom line is written from.

    Built by the live artifact and by the stored read-back alike, so a claim
    reads the same whether it was just verified or is being looked up later.
    """

    claim_text: str
    label: str
    state: str
    findings: tuple[Finding, ...]
    reconstruction: str | None
    sources: tuple[Source, ...]
    sweep_ran: bool
    flips: tuple[Flip, ...]
    sweep_reason: str
    implied: tuple[str, ...] = ()
    decomposed: bool = True
    #: What the claim was measured against, as "measure (custodian)".
    measures: tuple[str, ...] = ()


# A line is a label and a run of segments. Each segment names the channel
# AC-7 checks it through: prose, the claimant's own words, a derived
# implication, or a figure with the retrieval behind it.
_Segment = tuple[str, str, "RetrievalId | None"]


def lines(basis: Basis) -> list[tuple[str, list[_Segment]]]:
    """The bottom line as labelled lines, in reading order."""
    _check_reconstruction(basis)
    out: list[tuple[str, list[_Segment]]] = []
    latest = _latest_per_series(basis.sources)
    compared = latest[-1] if len(latest) == 1 else None

    label_text = basis.label.replace("_", " ").upper()
    if basis.state == "rejected":
        out.append(("Verdict", [_t("none published. A reviewer rejected the proposed label.")]))
    else:
        out.append(("Verdict", [_t(f"{label_text}. {_meaning(basis)}")]))

    # The evidence that would settle it: which published measure, from whom.
    if basis.measures:
        out.append(("Checked against", [_t("; ".join(basis.measures) + ".")]))
    else:
        out.append(("Checked against", [_t(
            "no official measure available here covers this claim."
        )]))

    for finding in basis.findings:
        line = _finding_line(finding, compared, latest)
        if line:
            out.append(line)

    for implication in basis.implied:
        out.append(("Implied, not checked", [("derived", implication, None)]))

    if basis.reconstruction is not None:
        anchor = latest[-1].retrieval_id if latest else None
        segment: _Segment = (
            ("sourced", basis.reconstruction, anchor) if anchor else _t(basis.reconstruction)
        )
        out.append(("Closest version the sources support", [segment]))
    elif any(f.status == "verified" for f in basis.findings):
        out.append(("Closest version the sources support", [_t(
            "none. What was confirmed does not add up to a statement on its own."
        )]))
    else:
        out.append(("Closest version the sources support", [_t(
            "none. Nothing in the claim was confirmed by a source."
        )]))

    out.append(("Tested against other readings", _disconfirmation(basis)))

    if latest:
        segments: list[_Segment] = []
        for i, source in enumerate(latest):
            if i:
                segments.append(_t("; "))
            segments.append((
                "sourced",
                f"{source.custodian_id} / {source.series_id}, revision "
                f"{source.revision_status}, retrieved {source.retrieved_at}",
                source.retrieval_id,
            ))
        segments.append(_t("."))
        out.append(("Sources", segments))
    else:
        out.append(("Sources", [_t("none. No source was consulted for this claim.")]))

    reviewed = (
        "This is the engine's proposed verdict, not yet reviewed by a person."
        if basis.state == "proposed"
        else "A person has reviewed this verdict; the record below says how."
    )
    provisional = (
        "It holds only for the figures as retrieved. A revised figure is pulled "
        "again, never served from memory, and reopens it."
        if latest
        else "A source that comes to cover this claim would reopen it."
    )
    out.append(("Open to correction", [_t(f"{reviewed} {provisional}")]))
    return out


def write(payload: Payload, basis: Basis) -> None:
    """Append the bottom line to a text payload, each segment on its channel."""
    payload.line(HEADING.upper())
    payload.line(f"  {LEAD}")
    for label, segments in lines(basis):
        payload.text(f"  {label}: ")
        _emit(payload, segments)
        payload.line()
    payload.line()


def as_text(basis: Basis) -> str:
    """The bottom line alone as scanned text, for the structured form.

    It is only ever placed beside the full record (``Artifact.to_dict``), and
    it goes through a payload's render so the structured form is scanned for
    numerals like every other output.
    """
    payload = Payload(claim_text=basis.claim_text)
    for label, segments in lines(basis):
        payload.text(f"{label}: ")
        _emit(payload, segments)
        payload.line()
    return payload.render()


def as_html(basis: Basis) -> str:
    """The bottom line as an HTML section.

    The text form is rendered first as the gate, exactly as ``render_html``
    runs ``render``: an unsourced figure raises before any markup exists.
    Figures link to their citation by retrieval id.
    """
    as_text(basis)
    e = html.escape
    out = [f'<section class="bottom-line"><h2>{e(HEADING)}</h2>',
           f'<p class="bottom-line-lead">{e(LEAD)}</p>']
    for label, segments in lines(basis):
        parts: list[str] = []
        for channel, value, rid in segments:
            if channel == "quoted":
                parts.append(f"<q>{e(value)}</q>")
            elif channel == "sourced" and rid is not None:
                parts.append(f'<a href="#retrieval-{e(str(rid))}">{e(value)}</a>')
            else:
                parts.append(e(value))
        out.append(f'<p><strong>{e(label)}:</strong> {"".join(parts)}</p>')
    out.append("</section>")
    return "\n".join(out)


# -- the parts -------------------------------------------------------------


def _t(value: str) -> _Segment:
    return ("text", value, None)


def _q(value: str) -> _Segment:
    return ("quoted", value.strip(), None)


def _figure(source: Source) -> _Segment:
    return (
        "sourced",
        f"{source.value} {source.unit} for {source.reference_period} "
        f"({source.custodian_id} / {source.series_id})",
        source.retrieval_id,
    )


def _emit(payload: Payload, segments: list[_Segment]) -> None:
    for channel, value, rid in segments:
        if channel == "quoted":
            payload.text("\u201c").quoted(value).text("\u201d")
        elif channel == "derived":
            payload.derived(value)
        elif channel == "sourced" and rid is not None:
            payload.sourced(value, rid)
        else:
            payload.text(value)


def _meaning(basis: Basis) -> str:
    """What the label means for this claim, in a sentence a reader can use.

    Calibrated to the evidence, not to the label's severity: Insufficient
    Data is stated as an answer and never as a suspicion of falsehood.
    """
    in_scope = [f for f in basis.findings if f.status != "out_of_scope"]
    statuses = {f.status for f in in_scope}
    label = basis.label
    if label == "accurate":
        return ("What can be checked matches the official record, and the conclusion "
                "still holds when the comparison is made the other ways the source accepts.")
    if label == "misleading":
        return ("The figures as stated check out, but the conclusion depends on how the "
                "comparison is made. Made another way the source accepts, it reverses.")
    if label == "substantially_inaccurate":
        return ("Part of what can be checked matches the official record, and part of it "
                "is contradicted by it.")
    if label == "false":
        return "What can be checked is contradicted by the official record."
    if label == "indeterminate":
        if "contested_by_definition" in statuses:
            series = _latest_per_series(basis.sources)
            if len(series) > 1:
                return ("Not settled either way. The claim could refer to more than "
                        "one measured thing, and their published figures differ.")
            if series:
                return ("Not settled either way. The comparison spans a point where "
                        "the source changed how the series is defined, and no linked "
                        "series bridges it.")
            return ("Not settled either way. The claim could refer to more than one "
                    "measured thing, or to a series whose definition changed.")
        if basis.reconstruction is None:
            return ("Not settled. The parts that check out do not add up to the "
                    "statement the claim makes.")
        return ("Unsupported as stated. What can be checked matches, but the conclusion "
                "could not be tested against other ways of making the comparison, so "
                "it is not confirmed.")
    # insufficient_data
    if not basis.decomposed or not basis.findings:
        return ("No official source available here covers this claim, so it is neither "
                "confirmed nor refuted. That is not a finding that it is false.")
    if not in_scope:
        return ("Nothing in it is a statement of fact that an official source available "
                "here could settle, so it is neither confirmed nor refuted. That is not "
                "a finding that it is false.")
    if statuses == {"unreachable"}:
        return ("The sources for this claim could not be reached this session, so it "
                "is neither confirmed nor refuted. That says nothing about whether it "
                "is true.")
    return ("No official source settles this claim, so it is neither confirmed nor "
            "refuted. That is not a finding that it is false.")


_NOT_CHECKABLE = {
    "opinion": "opinion or evaluative language, with no fact in it to check.",
    "prediction": "a prediction, and no record of the future exists yet.",
    "causal": (
        "a claim about causes. No official record measures how much of an outcome "
        "a cause produced."
    ),
}


def _finding_line(
    finding: Finding, compared: Source | None, latest: list[Source]
) -> tuple[str, list[_Segment]] | None:
    status, kind = finding.status, finding.kind
    fragment = _q(finding.fragment)

    if status == "verified":
        if kind == "time_period":
            # A period scopes the comparison; it asserts nothing on its own.
            return None
        if kind in ("quantity", "discrete_count") and compared is not None:
            if finding.band == "B":
                return ("True", [fragment, _t(
                    " is right to within rounding, not exactly. The published figure is "
                ), _figure(compared), _t(".")])
            return ("True", [fragment, _t(" matches the published figure, "),
                             _figure(compared), _t(".")])
        if kind == "direction":
            return ("True", [fragment, _t(
                " holds. Over the retrieved series the figure moved the way the claim says."
            )])
        if kind == "superlative":
            return ("True", [fragment, _t(" holds against the full retrieved series.")])
        return ("True", [fragment, _t(" is supported by the record.")])

    if status == "contradicted":
        if kind in ("quantity", "discrete_count") and compared is not None:
            return ("False", [fragment, _t(" is contradicted. The published figure is "),
                              _figure(compared), _t(".")])
        if kind == "direction":
            return ("False", [fragment, _t(
                " is contradicted. Over the retrieved series the figure moved the other "
                "way, or not at all."
            )])
        if kind == "superlative":
            return ("False", [fragment, _t(
                " is contradicted. The latest figure is not the extreme of the series."
            )])
        return ("False", [fragment, _t(" is contradicted by the record.")])

    if status == "contested_by_definition":
        segments: list[_Segment] = [fragment]
        if latest:
            segments.append(_t(
                " cannot be settled as stated. The published figures it could be "
                "compared with are "
            ))
            for i, source in enumerate(latest):
                if i:
                    segments.append(_t("; "))
                segments.append(_figure(source))
            segments.append(_t(". The claim does not say which it means."))
        else:
            segments.append(_t(
                " cannot be settled as stated. It could mean more than one measured "
                "thing, and they differ."
            ))
        return ("Cannot be settled", segments)

    if status == "unverified":
        return ("Not checked", [fragment, _t(
            " \u2014 the source was reached and publishes no figure covering it."
        )])
    if status == "unreachable":
        return ("Not checked", [fragment, _t(
            " \u2014 the source could not be reached this session."
        )])
    if status == "out_of_scope":
        return ("Not checkable", [fragment, _t(
            f" \u2014 {_NOT_CHECKABLE.get(kind, 'outside what an official record can settle.')}"
        )])
    return ("Not checked", [fragment, _t(" \u2014 no outcome was recorded for it.")])


def _disconfirmation(basis: Basis) -> list[_Segment]:
    """§9.3's sweep, restated: did the conclusion survive other readings?"""
    if basis.flips:
        segments: list[_Segment] = [_t(
            "the conclusion was checked again against the other baselines and time "
            "windows the source accepts, and it reverses under "
        )]
        for i, flip in enumerate(basis.flips):
            if i:
                segments.append(_t(", "))
            segments.append(("sourced", f"{flip.test}: {flip.alternative}", flip.retrieval_id))
        segments.append(_t(" (the robustness sweep below shows each comparison)."))
        return segments
    if not any(f.status in ("verified", "contradicted") for f in basis.findings):
        return [_t("not attempted, since nothing in the claim was compared with a figure.")]
    if basis.sweep_ran:
        return [_t(
            "the conclusion was checked again against every other baseline and time "
            "window the source accepts, and holds under all of them."
        )]
    reason = (basis.sweep_reason or "no alternative comparison was recorded").rstrip(".")
    return [_t(f"not possible here: {reason}.")]


def _latest_per_series(sources: tuple[Source, ...]) -> list[Source]:
    """The most recent figure of each cited series, in first-cited order."""
    order: list[tuple[str, str]] = []
    latest: dict[tuple[str, str], Source] = {}
    for source in sources:
        key = (source.custodian_id, source.series_id)
        if key not in latest:
            order.append(key)
        latest[key] = source
    return [latest[key] for key in order]


def _check_reconstruction(basis: Basis) -> None:
    """The same rule the full render applies: every numeral has a retrieval."""
    if basis.reconstruction is None:
        return
    sourced = {
        numeral
        for source in basis.sources
        for numeral in _NUMERAL.findall(f"{source.value} {source.reference_period}")
    }
    unaccounted = [t for t in _NUMERAL.findall(basis.reconstruction) if t not in sourced]
    if unaccounted:
        raise UnsourcedFigure(
            f"the reconstruction carries {sorted(set(unaccounted))} with no matching "
            "retrieval, so the bottom line cannot state it (§3)"
        )
