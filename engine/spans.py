"""Spans of claim text.

Spec §9.7.1 is the anchoring rule: every derived element cites a span of the
original claim text, and — as extended in v0.4 — so does every ordinary
element.  A span is the analogue of a retrieval id.  Where §3 says every
*figure* traces to a retrieval, §9.7.1 says every *claim fragment* traces to
a span, and both replace "the system produced this" with "here is where it
came from."
"""

from __future__ import annotations

from dataclasses import dataclass


class UnresolvableSpan(ValueError):
    """Raised when a span does not identify the text it claims to."""


@dataclass(frozen=True, slots=True)
class Span:
    """A half-open character range over a claim's text."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise UnresolvableSpan(f"negative start: {self.start}")
        if self.end <= self.start:
            raise UnresolvableSpan(f"empty or inverted span: [{self.start}, {self.end})")

    def resolve(self, claim_text: str) -> str:
        """Return the substring this span identifies, or raise.

        AC-16 and AC-18 both require that the substring "occurs verbatim in
        the original claim text **at that position**".  Resolution is
        positional for that reason: a span that merely finds its text
        somewhere else in the claim has not been verified, it has been
        searched for, and searching is what a retrofitted span does.
        """
        if self.end > len(claim_text):
            raise UnresolvableSpan(
                f"span [{self.start}, {self.end}) runs past text of length {len(claim_text)}"
            )
        return claim_text[self.start : self.end]

    def __len__(self) -> int:
        return self.end - self.start
