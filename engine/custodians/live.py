"""Wiring real adapters, at the composition root and nowhere else.

Kept apart from :mod:`engine.custodians.base` on purpose. The verification
path imports ``base`` and must not, by any static route, reach a module that
imports a network primitive — AC-14 asserts exactly that, and it holds only
while nothing on that path pulls this module in.

So this is imported by the CLI and by tests, never by the pipeline. An adapter
reaches a custodian because a person wired it up, not because a verification
stage went looking for one.
"""

from __future__ import annotations

from engine.custodians.base import CustodianAdapter


def build_live_custodians() -> dict[str, CustodianAdapter]:
    """Adapters for custodians this deployment can actually reach.

    The import is inside the function so that merely importing this module
    does not pull a network client into whatever imported it.
    """
    from engine.custodians.boi import BankOfIsraelAdapter

    return {"boi": BankOfIsraelAdapter()}
