#!/usr/bin/env python3
"""Mint or revoke a per-worker LightWorker credential.

    python3 scripts/bridgeV002/mint_worker_token.py --worker-id svend3060
    python3 scripts/bridgeV002/mint_worker_token.py --worker-id svend3060 --revoke

The token is printed EXACTLY ONCE and never stored -- Father keeps only its
sha256, so a leaked database leaks no credential. Install the printed token
on the worker (`LIGHTWORKER_AUTH_TOKEN="..."` in ~/.lightworker-auth) and
restart its daemon.

Minting the FIRST token flips Father out of legacy mode: from then on the
shared token no longer authenticates anyone. Mint, install, restart -- in
that order, or the worker locks itself out between the first two steps.
Re-minting for the same worker revokes its previous tokens first, so a
worker holds at most one active credential.
"""

import argparse
import hashlib
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
import config  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--revoke", action="store_true",
                    help="Revoke all active tokens for the worker; mint none")
    args = ap.parse_args()

    conn = sqlite3.connect(config.get_db_path())
    now = datetime.now(timezone.utc).isoformat()
    revoked = conn.execute(
        "UPDATE lightworker_worker_tokens SET revoked_at = ? "
        "WHERE worker_id = ? AND revoked_at IS NULL",
        (now, args.worker_id)).rowcount
    if revoked:
        print(f"revoked {revoked} active token(s) for {args.worker_id}")
    if args.revoke:
        conn.commit()
        return 0

    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO lightworker_worker_tokens "
        "(worker_id, token_hash, created_at) VALUES (?, ?, ?)",
        (args.worker_id, hashlib.sha256(token.encode()).hexdigest(), now))
    conn.commit()
    print(f"worker:  {args.worker_id}")
    print(f"token:   {token}")
    print("shown once — install on the worker and restart its daemon NOW;")
    print("the shared token stopped authenticating the moment this row landed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
