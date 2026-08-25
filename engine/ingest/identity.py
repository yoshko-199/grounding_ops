"""The half of ingest provenance that never crosses into verification.

Spec §9.8.1.  This module is the one thing in the tree that
:mod:`engine.verification` may not reach, transitively or otherwise, and
``tests/conformance/test_ac06.py`` asserts exactly that over the import
graph.

Venue is the field worth understanding.  It is nominally location metadata
and functionally an identification of affiliation — "speech at the party
conference" names a party while looking like a place.  §9.8 rejects the
obvious fix of passing provenance downstream under a convention that the
pipeline "won't look at the name", because that convention fails the moment
someone adds a feature.  Venue lives here instead, on the side of the split
that has no downstream reader.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClaimantIdentity:
    """Who said it, where, and to whom.  Retained, displayed, never routed.

    This information is not deleted — a verification is *about* a claim
    someone made, and the record should say so.  It is separated, which is a
    different thing: it reaches presentation without ever reaching the path
    that decides which custodian answers the question.
    """

    name: str | None = None
    affiliation: str | None = None
    role: str | None = None
    venue: str | None = None
    audience: str | None = None

    @property
    def is_anonymous(self) -> bool:
        """True when no attribution was supplied.

        AC-6 requires that an unattributed run produce byte-identical output
        to an attributed one, so this is a property of presentation only.
        """
        return not any((self.name, self.affiliation, self.role, self.venue, self.audience))
