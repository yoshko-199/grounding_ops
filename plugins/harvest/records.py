"""What a harvest produces, and what it refuses to become.

A harvested record is a **claim**: something a person said, that someone might
want checked.  It is never a figure, an observation, or a citation.  Nothing in
this module has a field that could hold one, which is the same technique
:mod:`engine.elements` uses to keep a derived element from carrying a status.

Two properties are enforced rather than documented, and both came out of
looking at how real aggregators publish claims:

* **A date is not a date until it is exact.**  Sources routinely display an
  approximate date where they could not establish the real one — the practice
  is common enough that the aggregator surveyed while designing this module
  states it openly in its own about page.  An approximate date is fine for
  browsing and fatal for verification, because §9.2's tolerance bands and
  §9.5's continuity check are both indexed on *when the claim was made*.  So
  :class:`CandidateClaim` will hand out a ``stated_at`` only when its
  precision is :attr:`DatePrecision.EXACT`, and raises otherwise.
* **The raw body is kept.**  Cleaning is recorded as a list of transforms
  rather than performed silently, because §9.7.1 anchors derived elements to
  spans of the original text and a span computed against quietly-rewritten
  text resolves to the wrong words.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class DatePrecision(Enum):
    """How well the source established when the claim was made.

    A closed set, because the interesting value is the middle one.  Collapsing
    ``APPROXIMATE`` into ``EXACT`` produces a corpus that looks dated and is
    not; collapsing it into ``UNKNOWN`` throws away the ordering information
    that makes an approximate date worth keeping at all.
    """

    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class TextTransform(Enum):
    """Every way the harvested text may differ from the body as received.

    Closed and versioned with this module, for the same reason
    :class:`engine.elements.DerivationOperation` is: an open set of
    transformations is an open licence to rewrite a claimant's words.
    """

    HTML_STRIPPED = "html-stripped"
    ENTITIES_DECODED = "entities-decoded"
    WHITESPACE_COLLAPSED = "whitespace-collapsed"


class UndatedClaim(Exception):
    """Raised when a claim without an exact date is asked for one."""


@dataclass(frozen=True, slots=True)
class Provenance:
    """Which source, account, and transport produced this record.

    ``backend`` is the field the prior art omits.  Where several transports
    serve one account they do not agree on formatting, and without this field
    a corpus mixes their outputs with no way to tell which convention any
    given record follows.
    """

    source_id: str
    account: str
    backend: str
    url: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        for name in ("source_id", "account", "backend"):
            if not getattr(self, name).strip():
                raise ValueError(f"provenance requires a non-empty {name}")


@dataclass(frozen=True, slots=True)
class CandidateClaim:
    """One harvested claim, with everything needed to audit where it came from.

    Note the fields that are absent: there is no verdict, no status, no
    figure, no retrieval id, and no custodian.  A harvested claim is an input
    to Stage 0 and nothing else, and the type makes any other use a type
    error rather than a review comment.
    """

    text: str
    raw: str
    provenance: Provenance
    transforms: tuple[TextTransform, ...] = ()
    published_at: date | None = None
    date_precision: DatePrecision = DatePrecision.UNKNOWN

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a claim with no text is not a claim")
        if self.date_precision is DatePrecision.UNKNOWN and self.published_at:
            raise ValueError(
                "a claim carrying a date must say how precisely that date is known; "
                "UNKNOWN with a date set is the combination that later reads as exact"
            )
        if self.date_precision is not DatePrecision.UNKNOWN and not self.published_at:
            raise ValueError(
                f"date_precision {self.date_precision.value!r} with no date is a "
                "precision claim about nothing"
            )

    @property
    def identity_key(self) -> str:
        """Stable identity across transports of the same account.

        The URL where there is one, because two transports serving one account
        agree on the link and disagree on everything else — one returns HTML,
        another returns it stripped, and a content hash would therefore treat
        one item as two.  Where there is no URL, the text is all there is.
        """
        if self.provenance.url:
            return self.provenance.url
        digest = hashlib.sha256(self.text.strip().encode("utf-8")).hexdigest()
        return f"{self.provenance.source_id}:{digest[:32]}"

    def stated_at(self) -> date:
        """The date this claim was made, or an exception.

        §9.2 bands and §9.5 continuity are both indexed on when the claim was
        made, so an approximate date used here does not degrade the answer —
        it produces a confident answer to a different question.  Refusing is
        the only reading that keeps the corpus honest, and the caller is left
        to decide whether to drop the claim or go and establish the date.
        """
        if self.date_precision is not DatePrecision.EXACT or self.published_at is None:
            raise UndatedClaim(
                f"claim from {self.provenance.source_id} has date precision "
                f"{self.date_precision.value!r}; a verification context needs an "
                "exact date, and an approximate one silently answers a different "
                "question"
            )
        return self.published_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "raw": self.raw,
            "transforms": [t.value for t in self.transforms],
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "date_precision": self.date_precision.value,
            "provenance": {
                "source_id": self.provenance.source_id,
                "account": self.provenance.account,
                "backend": self.provenance.backend,
                "url": self.provenance.url,
                "fetched_at": self.provenance.fetched_at.isoformat(),
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CandidateClaim:
        prov = payload["provenance"]
        published = payload.get("published_at")
        return cls(
            text=payload["text"],
            raw=payload.get("raw", payload["text"]),
            provenance=Provenance(
                source_id=prov["source_id"],
                account=prov["account"],
                backend=prov["backend"],
                url=prov.get("url", ""),
                fetched_at=datetime.fromisoformat(prov["fetched_at"]),
            ),
            transforms=tuple(
                TextTransform(t) for t in payload.get("transforms", ())
            ),
            published_at=date.fromisoformat(published) if published else None,
            date_precision=DatePrecision(payload.get("date_precision", "unknown")),
        )
