"""The harvested corpus on disk: JSON Lines, keyed by claim identity.

A corpus is a test input, not a data set the engine reads at runtime.  Nothing
under ``engine/`` imports this module, and
``tests/conformance/test_plugin_isolation.py`` fails if that ever changes.

Merging rather than appending is the one decision here worth stating.  A
source that corrects or re-dates a claim should update the record, not add a
second one, because a corpus with both is a corpus that reports two claims
where one was made — and derivation coverage measured against it would then
be measured against a denominator that is partly an artefact of how often the
harvest ran.
"""

from __future__ import annotations

import json
from pathlib import Path

from plugins.harvest.records import CandidateClaim


def read(path: Path) -> tuple[CandidateClaim, ...]:
    """Load a corpus. A missing file is an empty corpus, not an error."""
    if not path.exists():
        return ()
    claims: list[CandidateClaim] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            claims.append(CandidateClaim.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"{path.name}:{number}: {exc}") from exc
    return tuple(claims)


def merge(
    existing: tuple[CandidateClaim, ...], harvested: tuple[CandidateClaim, ...]
) -> tuple[CandidateClaim, ...]:
    """Combine two corpora, letting the newly harvested record win.

    Order is stable: existing claims keep their position, new ones are
    appended.  A corpus whose line numbers shift on every harvest is a corpus
    whose diffs are unreadable.
    """
    index = {claim.identity_key: position for position, claim in enumerate(existing)}
    merged = list(existing)
    for claim in harvested:
        position = index.get(claim.identity_key)
        if position is None:
            index[claim.identity_key] = len(merged)
            merged.append(claim)
        else:
            merged[position] = claim
    return tuple(merged)


def write(path: Path, claims: tuple[CandidateClaim, ...]) -> int:
    """Write a corpus, returning the number of records written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(claim.to_dict(), ensure_ascii=False, sort_keys=True)
        for claim in claims
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)
