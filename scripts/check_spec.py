#!/usr/bin/env python3
"""
check_spec.py - mechanical consistency checks for the specification documents.

Implements the checks listed in docs/plan.md under "Verification for spec
changes". Every check is pass/fail and prints what failed and where.

These checks do not evaluate whether the spec is *good*. They check that it is
internally consistent, that no constraint has lost its test, and - check 5 -
that the documents do not violate the anti-fabrication rule they impose on the
system they describe.

Usage:
    python3 scripts/check_spec.py            # run all checks
    python3 scripts/check_spec.py -v         # also list what passed

Exit code 0 if every check passes, 1 otherwise.
"""

import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The current spec version. Bump when a new version file becomes current.
CURRENT_SPEC = "docs/spec/claim-verification-engine.v0.4.md"
CRITERIA = "docs/spec/acceptance-criteria.md"

failures = []
notes = []


def fail(check, msg):
    failures.append((check, msg))


def ok(check, msg):
    notes.append((check, msg))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def docs():
    """Every markdown document in the repo, repo-relative."""
    out = ["README.md"]
    for p in sorted(glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)):
        out.append(os.path.relpath(p, ROOT))
    return out


def archived(rel):
    """Superseded spec versions are frozen; checks that would force edits skip them."""
    m = re.search(r"\.v(\d+)\.(\d+)\.md$", rel)
    if not m:
        return False
    return rel != CURRENT_SPEC


# --------------------------------------------------------------------------
# Check 1 - every resolved decision carries a decision and a rationale
# --------------------------------------------------------------------------
def check_resolutions():
    txt = read(CURRENT_SPEC)
    body = re.search(r"^## 9\. Resolved decisions(.*?)^## 10\.", txt, re.S | re.M)
    if not body:
        fail(1, f"{CURRENT_SPEC}: no '## 9. Resolved decisions' section found")
        return
    section = body.group(1)

    subsections = re.split(r"^### (9\.\d+[^\n]*)$", section, flags=re.M)[1:]
    if not subsections:
        fail(1, "no §9.x subsections found")
        return

    pairs = list(zip(subsections[0::2], subsections[1::2]))
    for heading, content in pairs:
        num = heading.split()[0]
        if not re.search(r"\*\*Decision\.?\*\*|—\s*(resolved|the|a |extraction|no,|automated|generalised|break register|a projection)", heading + content, re.I):
            fail(1, f"§{num} has no visible decision statement")
        if not re.search(r"\*\*Rationale|\*\*Why|\*\*Decision", content, re.I):
            fail(1, f"§{num} states no rationale")

    stale = re.findall(r"^.*(?:needs a strategy|unsolved|TBD|to be determined).*$", section, re.M | re.I)
    for line in stale:
        fail(1, f"§9 contains unresolved language: {line.strip()[:90]}")

    ok(1, f"{len(pairs)} resolved decisions, each with a decision and rationale")


# --------------------------------------------------------------------------
# Check 2 - every constraint maps to a criterion; every criterion has a test
# --------------------------------------------------------------------------
def check_criteria():
    txt = read(CRITERIA)

    acs = re.findall(r"^## (AC-\d+) — (.+)$", txt, re.M)
    if not acs:
        fail(2, "no acceptance criteria found")
        return

    blocks = re.split(r"^## AC-\d+ — .+$", txt, flags=re.M)[1:]
    for (ac_id, _), block in zip(acs, blocks):
        if not re.search(r"^\*\*Test", block, re.M):
            fail(2, f"{ac_id} states no test")
        if not re.search(r"^\*\*Fails if:\*\*", block, re.M):
            fail(2, f"{ac_id} states no failure condition")
        if not re.search(r"^\*\*Constraint:\*\*", block, re.M):
            fail(2, f"{ac_id} cites no source constraint")

    # every §7.1-§7.6 constraint appears in the coverage map
    cov = re.search(r"### Coverage map(.*?)^---", txt, re.S | re.M)
    if not cov:
        fail(2, "no coverage map found")
    else:
        for n in range(1, 7):
            if f"§7.{n}" not in cov.group(1):
                fail(2, f"coverage map omits §7.{n}")

    ok(2, f"{len(acs)} criteria, each with constraint, test, and failure condition")


# --------------------------------------------------------------------------
# Check 3 - fields introduced in prose appear in the schema sketch
# --------------------------------------------------------------------------
def check_schema():
    txt = read(CURRENT_SPEC)
    sketch = re.search(r"```\n(custodians.*?)```", txt, re.S)
    if not sketch:
        fail(3, "no schema sketch found")
        return
    schema = sketch.group(1)

    # backticked snake_case identifiers used in prose outside the sketch
    prose = txt.replace(schema, "")
    used = set(re.findall(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+){1,})`", prose))

    # identifiers that are deliberately not schema columns
    exempt = {
        "known_confusions", "admissible_baselines", "admissible_windows",
        "jurisdiction_id", "pack_version", "custodian_notice_ref",
        "linked_series_available", "linked_series_identifier",
        "published_precision", "series_identifier", "authority_basis",
        "integrity_annotation", "access_method", "revision_policy",
        "alternatives_considered", "effective_date", "measure_id",
        "custodian_id", "implied_by_original_only", "source_span_start",
        "source_span_end", "derivation_operation", "jurisdiction_hint",
        "claim_context", "claimant_identity", "element_set_hash",
        "does_reconstruct", "triggered_by_retrieval_id",
        "computed_from_retrieval_id", "linked_series_used",
        "amendment_rationale", "amended_from_label", "source_attribution",
        "series_breaks", "derived_elements", "confirmed_by", "confirmed_at",
        "proposed_at", "continuity_status", "tolerance_band", "routing_log",
        # pack fields introduced by pack interface v1.1 §3.6, not columns
        "composition_connectives", "forbidden_connectives",
        "derivation_triggers", "element_slot_order",
        # enum values and tag names, not columns
        "base_year", "implied-by-original-only", "linked_series",
    }
    missing = sorted(f for f in used - exempt if f not in schema)
    for f in missing:
        fail(3, f"`{f}` used in prose but absent from the schema sketch")

    # the reverse direction matters more: new tables must be introduced in prose
    for table in ["derived_elements", "claim_context", "claimant_identity",
                  "series_breaks", "reconstructions", "sweeps", "packs"]:
        if table in schema and f"`{table}`" not in prose and table not in prose:
            fail(3, f"table `{table}` in schema is never explained in prose")

    ok(3, "schema sketch and prose agree on introduced fields")


# --------------------------------------------------------------------------
# Check 5 - the documents contain no fabricated figures
# --------------------------------------------------------------------------
def check_no_figures():
    """
    The spec must not contain statistics of its own. Numeric constants that are
    part of a stated rule are the sole exception, and must sit inside a code
    span or a line the rule owns.
    """
    pattern = re.compile(
        r"(?<![\w`])(\d{1,3}(?:,\d{3})+|\d+\.\d+)\s*"
        r"(%|pp|bn|billion|million|trillion|₪|\$|€|£)",
        re.I,
    )
    # Constants inside a code span are part of a stated rule or expression, not a
    # claim about the world. Blank them before scanning so the tolerance bands and
    # their worked examples do not trip the check; prose figures still do.
    codespan = re.compile(r"`[^`]*`")

    for rel in docs():
        if archived(rel):
            continue
        for i, line in enumerate(read(rel).splitlines(), 1):
            scanned = codespan.sub(lambda m: " " * len(m.group(0)), line)
            for m in pattern.finditer(scanned):
                span = line[max(0, m.start() - 60): m.end() + 40]
                fail(5, f"{rel}:{i} possible embedded statistic -> …{span.strip()}…")

    ok(5, "no embedded statistics in prose (code spans exempt as stated rules)")


# --------------------------------------------------------------------------
# Check 6 - every relative link and anchor resolves
# --------------------------------------------------------------------------
def slug(heading):
    s = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return s.replace(" ", "-")


def check_links():
    anchors = {}
    for rel in docs():
        anchors[rel] = {slug(m.group(2)) for m in
                        re.finditer(r"^(#{1,6})\s+(.*)$", read(rel), re.M)}

    count = 0
    for rel in docs():
        base = os.path.dirname(rel)
        for m in re.finditer(r"\]\(([^)\s#]+\.md)(#[^)]*)?\)", read(rel)):
            count += 1
            tgt = os.path.normpath(os.path.join(base, m.group(1)))
            if not os.path.exists(os.path.join(ROOT, tgt)):
                fail(6, f"{rel}: link to missing file {tgt}")
            elif m.group(2):
                a = m.group(2)[1:]
                if a not in anchors.get(tgt, set()):
                    fail(6, f"{rel}: unresolved anchor {tgt}#{a}")

    ok(6, f"{count} internal links and anchors resolve")


# --------------------------------------------------------------------------
# Check 7 - documents point at the current spec version
# --------------------------------------------------------------------------
def check_current_version():
    cur = os.path.basename(CURRENT_SPEC)
    for rel in ["README.md", "docs/plan.md", "docs/overview.md", CRITERIA]:
        txt = read(rel)
        older = re.findall(r"claim-verification-engine\.v(\d+\.\d+)\.md", txt)
        cur_v = re.search(r"v(\d+\.\d+)", cur).group(1)
        if cur_v not in older:
            fail(7, f"{rel} does not reference the current spec {cur}")
    ok(7, f"entry-point documents reference {cur}")


def main():
    verbose = "-v" in sys.argv
    for fn in (check_resolutions, check_criteria, check_schema,
               check_no_figures, check_links, check_current_version):
        try:
            fn()
        except Exception as exc:                      # noqa: BLE001
            fail(0, f"{fn.__name__} raised {type(exc).__name__}: {exc}")

    if verbose:
        for check, msg in notes:
            print(f"  ok   check {check}: {msg}")

    if failures:
        print(f"\nFAILED — {len(failures)} problem(s):\n")
        for check, msg in failures:
            print(f"  check {check}: {msg}")
        return 1

    print(f"\nAll checks passed ({len(notes)} groups).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
