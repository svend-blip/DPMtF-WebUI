-- 058_bridge_dispatch_queue.sql
-- Add the bridge dispatch queue table for the bridge-broker seam.
--
-- The bridge broker (scripts/bridgeV002/bridge_broker.py) is the narrow
-- host-side capability that lets a sandboxed role (e.g. super-deep-deep4
-- running inside the DeepSeek Harness workspace-write mount rooted at
-- /home/svend/DPMtF-WebUI) request a role-to-role transition without
-- gaining unrestricted host filesystem or host tmux access.
--
-- The supervisor cannot write /home/svend/flows (read-only mount) and
-- cannot see the host tmux socket /tmp/tmux-1000 (invisible mount). What
-- it CAN do is write to /home/svend/DPMtF-WebUI/databases/dpmtf.db (the
-- DB). The broker's --enqueue mode writes a row to this table; the
-- broker's --daemon mode (a host-side deployment step) polls the table
-- and dispatches each pending row by invoking dispatch.py, which DOES
-- have the host capabilities.
--
-- The dispatch.py manual/Human recovery path is unchanged. The chain
-- advancement block (next_signal_cmd in dispatch.py) is rewritten to call
-- bridge_broker.py --enqueue instead of dispatch.py --signal-complete,
-- so the supervisor's chain_advancement writes a queue row rather than
-- trying to perform the host-side dispatch itself.
--
-- The evidence gate and scope-fence validation are preserved: the
-- broker's --enqueue only writes a row, and the existing dispatch.py
-- flow continues to validate the handoff file (dispatch.py:signal_send
-- line 3149-3166) and to invoke the gate on deliverable rejection
-- (dispatch.py:_handle_gate_rejection line 1276+). The broker does not
-- disable or bypass either.
--
-- Status transitions:
--   pending    -> processing  (broker claims the row)
--   processing -> completed   (dispatch.py returned 0)
--   processing -> failed      (dispatch.py returned non-zero, error_msg set)
--
-- Idempotent: CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS bridge_dispatch_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    handoff_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('signal-send', 'signal-complete', 'signal-escalation', 'signal-answer')),
    handoff_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    processed_at TEXT,
    error_msg TEXT,
    broker_pid INTEGER
);

CREATE INDEX IF NOT EXISTS bridge_dispatch_queue_status_idx
    ON bridge_dispatch_queue(status, id);

CREATE INDEX IF NOT EXISTS bridge_dispatch_queue_flow_idx
    ON bridge_dispatch_queue(flow_key, status, id);
