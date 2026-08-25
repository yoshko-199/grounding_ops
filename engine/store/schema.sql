-- Persistence model — spec §8.
--
-- "The database stores retrieval events, not facts. This distinction is the
-- whole design."
--
-- Every table below follows from that sentence. `retrievals` carries a TTL
-- and a revision status because a cached figure reused without re-checking
-- is functionally identical to a figure recalled from model memory — the
-- exact failure §3 exists to prevent. `verdicts` carries a validity window
-- rather than a boolean, because "Verified" is always "verified against
-- series X, revision Y, as of date Z".
--
-- Note what is split: claim_context and claimant_identity are two tables,
-- not one table with a convention (§9.3 in v0.3, §9.8.1 here). A single
-- field excluded by convention passes AC-6 until someone adds a feature;
-- two tables cannot be conflated by accident.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS packs (
    id              TEXT PRIMARY KEY,
    jurisdiction_id TEXT NOT NULL,
    version         TEXT NOT NULL,
    maintainer      TEXT NOT NULL,
    loaded_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS custodians (
    id              TEXT PRIMARY KEY,
    pack_id         TEXT NOT NULL REFERENCES packs(id),
    name            TEXT NOT NULL,
    mandate         TEXT NOT NULL,
    cadence         TEXT NOT NULL,
    revision_policy TEXT NOT NULL,
    access_method   TEXT NOT NULL,
    integrity_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measures (
    id                  TEXT PRIMARY KEY,
    pack_id             TEXT NOT NULL REFERENCES packs(id),
    name                TEXT NOT NULL,
    definition          TEXT NOT NULL,
    custodian_id        TEXT NOT NULL REFERENCES custodians(id),
    unit                TEXT NOT NULL,
    published_precision REAL NOT NULL,
    discrete            INTEGER NOT NULL
);

-- The crossing half of provenance. Every column is a code or a date; AC-17
-- asserts the absence of free text, and that holds only without exception.
CREATE TABLE IF NOT EXISTS claim_context (
    id                TEXT PRIMARY KEY,
    jurisdiction_hint TEXT,
    language          TEXT NOT NULL,
    stated_at         TEXT NOT NULL
);

-- The non-crossing half. Retained and displayed; never routed.
CREATE TABLE IF NOT EXISTS claimant_identity (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    affiliation TEXT,
    role        TEXT,
    venue       TEXT,
    audience    TEXT
);

CREATE TABLE IF NOT EXISTS claims (
    id                  TEXT PRIMARY KEY,
    text                TEXT NOT NULL,
    stated_at           TEXT,
    type                TEXT NOT NULL CHECK (type IN ('original', 'reconstructed', 'derived')),
    claim_context_id    TEXT REFERENCES claim_context(id),
    claimant_identity_id TEXT REFERENCES claimant_identity(id)
);

CREATE TABLE IF NOT EXISTS elements (
    id                TEXT PRIMARY KEY,
    claim_id          TEXT NOT NULL REFERENCES claims(id),
    fragment          TEXT NOT NULL,
    kind              TEXT NOT NULL,
    measure_id        TEXT,
    status            TEXT,
    tolerance_band    TEXT,
    continuity_status TEXT,
    -- v0.4, §9.7.1 as extended. An element with no span is inadmissible.
    source_span_start INTEGER NOT NULL,
    source_span_end   INTEGER NOT NULL,
    CHECK (source_span_end > source_span_start)
);

-- Deliberately separate from `elements` (§9.7.4). No status column, no
-- tolerance band, no continuity status, and no retrieval foreign key. The
-- absence of those columns is the guarantee.
CREATE TABLE IF NOT EXISTS derived_elements (
    id                   TEXT PRIMARY KEY,
    from_claim_id        TEXT NOT NULL REFERENCES claims(id),
    text                 TEXT NOT NULL,
    tag                  TEXT NOT NULL,
    state                TEXT NOT NULL,
    source_span_start    INTEGER NOT NULL,
    source_span_end      INTEGER NOT NULL,
    derivation_operation TEXT NOT NULL,
    confirmed_by         TEXT,
    confirmed_at         TEXT,
    CHECK (source_span_end > source_span_start)
);

CREATE TABLE IF NOT EXISTS retrievals (
    id                 TEXT PRIMARY KEY,
    element_id         TEXT,
    custodian_id       TEXT NOT NULL,
    figure             TEXT NOT NULL,
    unit               TEXT NOT NULL,
    series_id          TEXT NOT NULL,
    reference_period   TEXT NOT NULL,
    revision_status    TEXT NOT NULL,
    retrieved_at       TEXT NOT NULL,
    ttl_expires_at     TEXT NOT NULL,
    caveat             TEXT,
    continuity_status  TEXT NOT NULL,
    linked_series_used TEXT,
    -- Set when a revision publishes over a provisional print (§8, AC-9).
    superseded_at      TEXT
);

CREATE INDEX IF NOT EXISTS retrievals_series
    ON retrievals (series_id, reference_period);

CREATE TABLE IF NOT EXISTS verdicts (
    id                  TEXT PRIMARY KEY,
    claim_id            TEXT NOT NULL REFERENCES claims(id),
    label               TEXT NOT NULL,
    rationale           TEXT NOT NULL,
    valid_from          TEXT NOT NULL,
    valid_until         TEXT,
    state               TEXT NOT NULL,
    proposed_at         TEXT NOT NULL,
    confirmed_by        TEXT,
    confirmed_at        TEXT,
    amended_from_label  TEXT,
    amendment_rationale TEXT
);

CREATE TABLE IF NOT EXISTS discards (
    id                     TEXT PRIMARY KEY,
    reconstructed_claim_id TEXT NOT NULL,
    element_id             TEXT NOT NULL REFERENCES elements(id),
    reason                 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    id            TEXT PRIMARY KEY,
    from_claim_id TEXT NOT NULL,
    to_claim_id   TEXT NOT NULL,
    tag           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_log (
    id                      TEXT PRIMARY KEY,
    element_id              TEXT NOT NULL,
    custodian_id            TEXT,
    rationale               TEXT NOT NULL,
    alternatives_considered TEXT NOT NULL,
    pack_id                 TEXT,
    pack_version            TEXT,
    -- §9.8.2 records which resolution rule fired.
    jurisdiction_rule       TEXT NOT NULL
);

-- The revision trajectory (§4 Stage 7). element_set_hash is what makes the
-- pure-function property checkable after the fact: two revisions sharing a
-- hash must share their text, and a revision whose text does not re-derive
-- from its recorded element set is evidence the reconstructor edited rather
-- than re-derived.
CREATE TABLE IF NOT EXISTS reconstructions (
    id                      TEXT PRIMARY KEY,
    claim_id                TEXT NOT NULL REFERENCES claims(id),
    revision                INTEGER NOT NULL,
    text                    TEXT NOT NULL,
    element_set_hash        TEXT NOT NULL,
    derived_at              TEXT NOT NULL,
    triggered_by_retrieval_id TEXT,
    does_reconstruct        INTEGER NOT NULL,
    UNIQUE (claim_id, revision)
);

CREATE TABLE IF NOT EXISTS series_breaks (
    id                      TEXT PRIMARY KEY,
    measure_id              TEXT NOT NULL,
    effective_date          TEXT NOT NULL,
    kind                    TEXT NOT NULL,
    custodian_notice_ref    TEXT NOT NULL,
    linked_series_available INTEGER NOT NULL,
    linked_series_identifier TEXT
);

-- The flip table (§9.3). Each row cites the retrieval it was computed from,
-- so the sweep is bound by §3 exactly as the primary verification is: a
-- sweep cell computed from anything other than a recorded retrieval is a
-- fabricated comparison.
CREATE TABLE IF NOT EXISTS sweeps (
    id                        TEXT PRIMARY KEY,
    claim_id                  TEXT NOT NULL REFERENCES claims(id),
    test                      TEXT NOT NULL,
    alternative               TEXT NOT NULL,
    conclusion_holds          INTEGER NOT NULL,
    computed_from_retrieval_id TEXT NOT NULL REFERENCES retrievals(id)
);
