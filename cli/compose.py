"""The composition shared by every front end: the CLI and the local web UI.

`cli/verify.py` did this inline, and a second front end copying it would be
two places for the same rules to drift apart in: which directory counts as
having packs, what an unopenable store looks like, and in which order an
artifact's tables are written. Everything here was lifted out of
`cli/verify.py` unchanged, messages included, so the CLI's tests pin the
behaviour for both front ends.

Adapters are deliberately *not* built here. Choosing which custodians a run
may reach (fixture, or `--live`) is the caller's decision, and tests
substitute adapters at the caller.
"""

from __future__ import annotations

import pathlib
import sqlite3
from datetime import date

from engine.codes import InvalidCode
from engine.context import ClaimContext
from engine.ingest.identity import ClaimantIdentity
from engine.ingest.split import RawProvenance, split
from engine.packs.registry import PackRegistry
from engine.pipeline import VerificationRun, verify
from engine.signoff import SignedVerdict, amend, confirm, reject
from engine.store.events import RetrievalStore
from engine.store.identity_writer import write_identity
from engine.store.signoff_writer import NoOpenVerdict, load_proposed, write_signoff
from engine.store.writer import write_pack, write_verification
from engine.verification.claim_verdict import Verdict

#: The three decisions §9.1 allows a reviewer. There is no fourth, and none of
#: these takes anything beneath the claim-level label.
DECISIONS = ("confirm", "amend", "reject")


class OperatorError(Exception):
    """Something the operator supplied is unusable: never a verdict.

    Insufficient Data is an answer and never raises this. A malformed date,
    a value that is not a code, missing packs or an unopenable store are
    problems with the request, reported as such by each front end: exit 2 on
    the command line, a form error in the browser.
    """


def parse_stated_at(value: str | None) -> date:
    try:
        return date.fromisoformat(value) if value else date.today()
    except ValueError:
        # A malformed date must not reach the pipeline: every tolerance band
        # and the continuity check are indexed on when the claim was made.
        raise OperatorError(
            f"not a date: {value!r}. Expected ISO format, for example 2021-06-01"
        ) from None


def split_provenance(raw: RawProvenance) -> tuple[ClaimContext, ClaimantIdentity]:
    try:
        return split(raw)
    except InvalidCode as exc:
        raise OperatorError(str(exc)) from None


def load_registry(packs: str) -> PackRegistry:
    # A pack directory that is missing, or that holds no packs, is an operator
    # error and not a verdict. Left unchecked it reaches the reader as
    # Insufficient Data — "no jurisdiction could be established" — which is
    # the correct sentence for a claim no pack covers and a badly misleading
    # one for a claim whose packs were simply never loaded. The two are
    # indistinguishable in the output, which is exactly the confusion §6.1
    # keeps Unverified and Unreachable apart to avoid.
    packs_dir = pathlib.Path(packs)
    if not packs_dir.is_dir():
        raise OperatorError(
            f"no pack directory at {packs!r}. Nothing would be loaded, "
            "and every claim would return Insufficient Data for the wrong reason"
        )
    if not any(packs_dir.glob("*.toml")):
        raise OperatorError(
            f"{packs!r} contains no pack files. Nothing would be loaded, "
            "and every claim would return Insufficient Data for the wrong reason"
        )
    return PackRegistry.from_directory(packs)


def open_store(path: str) -> RetrievalStore:
    try:
        if path != ":memory:":
            pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        return RetrievalStore(path)
    except (OSError, sqlite3.Error) as exc:
        # An unwritable directory, a path that is already a directory, a
        # corrupt database, or a concurrent run holding the lock. A traceback
        # out of the store constructor reads as a crash in the engine, which
        # is the one thing it is not.
        raise OperatorError(f"cannot open retrieval store {path!r}: {exc}") from None


def verify_and_persist(
    claim: str,
    context: ClaimContext,
    identity: ClaimantIdentity,
    registry: PackRegistry,
    store: RetrievalStore,
    adapters: dict,
) -> VerificationRun:
    """Verify, then write every table the run produced.

    Persistence is composition-root bookkeeping, not a verification rule, so
    it happens here rather than inside `verify` — `engine.store.writer` is
    not importable from `engine.verification` for exactly that reason.
    Identity is written by a second, separate module, because it is the one
    that imports `engine.ingest.identity`; `verify` itself only ever sees the
    context.
    """
    run = verify(claim, context, registry, adapters, store)
    if run.decision and run.decision.pack:
        write_pack(store, run.decision.pack)
    write_verification(store, run)
    write_identity(store, run.claim_id, identity)
    return run


class NoOpenProposal(OperatorError):
    """The claim has no verdict awaiting review: already decided, or never verified."""


def sign_off_stored(
    store: RetrievalStore,
    claim_id: str,
    action: str,
    reviewer: str,
    label: Verdict | None = None,
    rationale: str = "",
) -> SignedVerdict:
    """Decide a stored claim's proposed verdict, and write the decision.

    The signature is the whole of what a reviewer can say: a decision, a
    name, and for an amendment a label and a reason. Nothing here, and
    nothing a front end could pass through here, names an element, a
    retrieval, the ledger or the sweep (§9.1, AC-10). The gate's own refusals
    (`GateViolation`: no reviewer, a figure in the rationale, an "amendment"
    that keeps the label) pass through unchanged, for the caller to report.
    """
    if action not in DECISIONS:
        raise OperatorError(f"unknown decision {action!r}; expected one of {', '.join(DECISIONS)}")
    proposal = load_proposed(store, claim_id)
    if proposal is None:
        raise NoOpenProposal(
            f"no open proposed verdict for claim id {claim_id!r}. "
            "Either it was never verified into this store, or it has already been "
            "signed off"
        )
    if action == "confirm":
        signed = confirm(proposal, reviewer)
    elif action == "reject":
        signed = reject(proposal, reviewer)
    else:
        if label is None:
            raise OperatorError("a new label is required to amend")
        signed = amend(proposal, label, rationale, reviewer)
    try:
        write_signoff(store, claim_id, signed)
    except NoOpenVerdict:
        # Decided by someone else between the load above and this write.
        raise NoOpenProposal(
            f"claim id {claim_id!r} was signed off by someone else while this "
            "decision was being made"
        ) from None
    return signed
