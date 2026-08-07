-- 035: Per-worker credentials (§27's "next step", now taken).
--
-- The shared LIGHTWORKER_AUTH_TOKEN proves the caller holds *a* secret;
-- it cannot say WHICH worker calls, so worker_id stayed self-asserted in
-- every request body. END-REPORT run 001 listed it among the known-missing.
--
-- Tokens are stored as sha256 hex digests -- Father never persists a
-- usable secret, and a leaked database does not leak credentials. The
-- token itself is printed exactly once by mint_worker_token.py.
--
-- Fallback semantics live in the router, not here: while this table is
-- EMPTY the shared token still works (rollout order: mint, install,
-- restart worker); the moment it has an active row, only per-worker
-- tokens authenticate. A revoked token is a row with revoked_at set --
-- kept, not deleted, so the record shows what was revoked when.

CREATE TABLE IF NOT EXISTS lightworker_worker_tokens (
    worker_id   TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL,
    revoked_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_worker_tokens_worker
    ON lightworker_worker_tokens(worker_id);
