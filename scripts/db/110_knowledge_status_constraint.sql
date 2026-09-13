-- 110_knowledge_status_constraint.sql
-- Deferred status constraint for knowledge_indexes (GOAL-DRAFT-021).
--
-- knowledge/maintenance.py writes three status values through
-- record_index: 'noop', 'changed', and 'missing'. detect_changes returns
-- exactly those three statuses, and the CLI's --record-index branch calls
-- record_index(..., plan.status) BEFORE its noop early-print, so a noop
-- plan is recorded as 'noop'. The refresh endpoint returns before recording
-- on 'noop', but the CLI does not; therefore the column must accept all
-- three.
--
-- The 107 default 'unknown' is deliberately NO LONGER allowed. It was a
-- placeholder left unconstrained until a lifecycle existed; that lifecycle
-- now exists. Omitting status on INSERT therefore fails this trigger:
-- SQLite BEFORE INSERT triggers see NEW.status as NULL when the value is
-- omitted, and this trigger treats NULL as not allowed. Callers must state
-- 'changed' or 'missing' explicitly.
--
-- Trigger names: GOAL-DRAFT-021 says "triggers named
-- knowledge_indexes_status_check". SQLite trigger names are schema-wide and
-- two triggers cannot share one name, so the two event triggers are
-- knowledge_indexes_status_check_insert and
-- knowledge_indexes_status_check_update. Both carry the GOAL's base name,
-- which is what TG3 greps for.
--
-- Idempotent: CREATE TRIGGER IF NOT EXISTS only, no DROP, no DELETE, no
-- ALTER, no BEGIN/COMMIT (migrate.py wraps each file in a transaction), and
-- no absolute machine paths.

CREATE TRIGGER IF NOT EXISTS knowledge_indexes_status_check_insert
BEFORE INSERT ON knowledge_indexes
FOR EACH ROW
WHEN NEW.status IS NULL OR NEW.status NOT IN ('noop', 'changed', 'missing')
BEGIN
    SELECT RAISE(ABORT,
        'knowledge_indexes.status must be ''noop'' or ''changed'' or ''missing''');
END;

CREATE TRIGGER IF NOT EXISTS knowledge_indexes_status_check_update
BEFORE UPDATE OF status ON knowledge_indexes
FOR EACH ROW
WHEN NEW.status IS NULL OR NEW.status NOT IN ('noop', 'changed', 'missing')
BEGIN
    SELECT RAISE(ABORT,
        'knowledge_indexes.status must be ''noop'' or ''changed'' or ''missing''');
END;
