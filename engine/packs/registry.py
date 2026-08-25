"""The loaded-pack registry.

Interface §2: packs are "not operator-configurable at runtime".  This
registry has no mutation API — no register, no update, no unload.  A registry
is built from a directory of pack files and is thereafter read-only, which is
what AC-3 means by asserting that mutation fails through "every configuration
surface": the surfaces do not exist rather than existing and refusing.

Spec §9.8.3 forbids a default jurisdiction, so lookup returns ``None`` rather
than falling back.  A default "is not a convenience — it is a silent
assumption that systematically mis-routes every claim originating elsewhere,
and it fails in the worst possible way: a confident, fully-cited verdict
retrieved from the wrong country's custodian."
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.codes import JurisdictionCode
from engine.packs.loader import load
from engine.packs.schema import Pack


@dataclass(frozen=True, slots=True)
class PackRegistry:
    """An immutable set of loaded packs, keyed by jurisdiction.

    Frozen rather than merely slotted.  ``__slots__`` alone restricts *which*
    attributes exist while still permitting assignment to them, which would
    leave the loaded rule set rebindable at runtime — the exact surface AC-3
    tests.  The underlying mapping is wrapped in a read-only proxy for the
    same reason: an immutable object holding a mutable dict is not immutable.
    """

    _packs: Mapping[str, Pack]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_packs", MappingProxyType(dict(self._packs)))

    @classmethod
    def from_directory(cls, directory: str | Path) -> PackRegistry:
        """Load every ``.toml`` pack in a directory.

        A pack that fails validation raises rather than being skipped.  A
        registry that silently drops an invalid pack routes some claims and
        drops others, which interface §3 identifies as worse than loading
        nothing at all.
        """
        directory = Path(directory)
        packs: dict[str, Pack] = {}
        for path in sorted(directory.glob("*.toml")):
            pack = load(path)
            key = str(pack.jurisdiction)
            if key in packs:
                raise ValueError(
                    f"two packs claim jurisdiction {key!r}: "
                    f"{packs[key].source_path} and {pack.source_path}"
                )
            packs[key] = pack
        return cls(packs)

    def get(self, jurisdiction: JurisdictionCode | None) -> Pack | None:
        """Resolve a jurisdiction to a pack, or ``None``.

        ``None`` in, ``None`` out.  There is no fallback, and an unresolvable
        jurisdiction becomes Insufficient Data upstream (§9.8.2 rule 4).
        """
        if jurisdiction is None:
            return None
        return self._packs.get(str(jurisdiction))

    def covers(self, jurisdiction: JurisdictionCode | None) -> bool:
        return self.get(jurisdiction) is not None

    @property
    def jurisdictions(self) -> tuple[str, ...]:
        return tuple(sorted(self._packs))

    def __len__(self) -> int:
        return len(self._packs)

    def __repr__(self) -> str:
        return f"PackRegistry({', '.join(self.jurisdictions) or 'empty'})"
