"""Readiness and result status tokens for the Harness Allocator.

The persistent terminal and the one-shot ``execute`` boundary share these
tokens so callers can compare statuses without importing the terminal loop.

``DUPLICATE_REQUEST`` is a terminal-only readiness outcome: it is what the
persistent loop reports (and returns to READY) when a request whose identity
was already completed arrives again without an explicit ``retry`` flag. It is
never returned by :func:`~harness_allocator.invoke.execute`.
"""

from __future__ import annotations

READY = "READY"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
ERROR = "ERROR"
DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
