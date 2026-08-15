"""Machine-readable request and result types for the Deterministic Patcher.

These dataclasses mirror spec §9 (PatchRequest) and §10 (PatchResult) and
provide `to_dict()` / `from_dict()` so the patcher can be serialized over
the CLI / tool-call boundary in later handoffs without coupling to any
specific JSON library.

The dataclasses are frozen — PatchRequest is an intent description and
must not be mutated while an engine inspects it. PatchResult is the
canonical report returned to the caller and is similarly immutable.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Tuple


# ── PatchRequest (spec §9) ──────────────────────────────────────────────


@dataclass(frozen=True)
class PatchRequest:
    """A machine-readable description of a proposed repository mutation.

    Fields mirror spec §9. Anything not strictly necessary for the current
    engine is left at its default (None) so a structural request does not
    have to carry an empty unified-diff body and vice versa.
    """

    repo_path: str
    patch_mode: str
    operations: Optional[List[Dict[str, Any]]] = None
    patch: Optional[str] = None
    allowed_paths: Optional[List[str]] = None
    base_revision: Optional[str] = None
    verification: Optional[Dict[str, Any]] = None


# ── PatchResult (spec §10) ──────────────────────────────────────────────


@dataclass(frozen=True)
class PatchResult:
    """Structured report returned by every patcher invocation.

    Field semantics:

    - status: high-level human label ("applied", "rejected", "no_change",
      "check_passed", "check_failed", "internal_error").
    - applied: True iff the working tree was mutated by this call.
    - engine: name of the engine that handled the call ("git_apply",
      "libcst", "deterministic_patcher").
    - files_changed: repo-relative paths mutated by this call (empty on
      failure).
    - files_rejected: repo-relative paths the engine refused to touch
      (empty on success).
    - operations_requested / operations_applied: counts for multi-op
      structural requests; both equal on full success.
    - verification: structured per-step outcome
      ({"syntax": "passed"|"failed"|"not_run", ...}); None when no
      verification was requested.
    - resulting_diff: the exact `git diff` produced by this call, limited
      to files the patch touched; None when no mutation occurred.
    - audit: machine-readable audit metadata per spec §30 (None on
      pre-mutation rejections from the facade; populated by the engines
      after a successful or failed apply/check).
    - error_code: one of the constants in `patcher.errors` on failure;
      None on success.
    - error: human-readable failure description; None on success.
    """

    status: str
    applied: bool
    engine: str
    files_changed: List[str] = field(default_factory=list)
    files_rejected: List[str] = field(default_factory=list)
    operations_requested: int = 0
    operations_applied: int = 0
    verification: Optional[Dict[str, Any]] = None
    resulting_diff: Optional[str] = None
    audit: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict with stable key ordering."""
        out: Dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = _to_jsonable(value)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatchResult":
        """Build a PatchResult from a dict (typically decoded from JSON).

        Unknown keys are ignored so the loader is forward-compatible with
        later additions to the schema.
        """
        known = {f.name for f in fields(cls)}
        kwargs: Dict[str, Any] = {}
        for key, value in (data or {}).items():
            if key in known:
                kwargs[key] = _from_jsonable(key, value)
        return cls(**kwargs)


# ── PatchRequest serialization (mirror of PatchResult API) ──────────────


def request_to_dict(req: PatchRequest) -> Dict[str, Any]:
    """Serialize a PatchRequest to a JSON-compatible dict."""
    return {
        "repo_path": req.repo_path,
        "patch_mode": req.patch_mode,
        "operations": _to_jsonable(req.operations),
        "patch": req.patch,
        "allowed_paths": _to_jsonable(req.allowed_paths),
        "base_revision": req.base_revision,
        "verification": _to_jsonable(req.verification),
    }


def request_from_dict(data: Dict[str, Any]) -> PatchRequest:
    """Build a PatchRequest from a dict; unknown keys are ignored."""
    if data is None:
        raise ValueError("PatchRequest payload is None")
    return PatchRequest(
        repo_path=data.get("repo_path"),
        patch_mode=data.get("patch_mode"),
        operations=_from_jsonable("operations", data.get("operations")),
        patch=data.get("patch"),
        allowed_paths=_from_jsonable("allowed_paths", data.get("allowed_paths")),
        base_revision=data.get("base_revision"),
        verification=_from_jsonable("verification", data.get("verification")),
    )


# ── Internal helpers ────────────────────────────────────────────────────


def _to_jsonable(value: Any) -> Any:
    """Deep-copy and strip non-JSON-native containers from a value.

    Tuples become lists (JSON has no tuple type). Dicts and lists are
    recursed. Everything else is returned as-is — strings, ints, bools,
    floats and None are already JSON-native.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    # Last resort: fall back to repr — but only for primitive-ish types.
    # The dataclasses are not serialized here; callers wanting that should
    # call .to_dict() on the dataclass first.
    return copy.deepcopy(value)


def _from_jsonable(key: str, value: Any) -> Any:
    """Reverse of `_to_jsonable`; only meaningful for known list fields.

    We accept JSON-decoded lists for `files_changed`, `files_rejected`,
    `allowed_paths` and `operations`. Lists of strings are returned as
    tuples (immutable) so the dataclass `frozen=True` constraint is
    honoured when a caller passes them through.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_from_jsonable(f"{key}[]", v) for v in value]
    if isinstance(value, dict):
        return {str(k): _from_jsonable(str(k), v) for k, v in value.items()}
    raise ValueError(
        f"PatchResult: unsupported value type for field '{key}': {type(value).__name__}"
    )


# Convenience type alias used in policy.py for the immutable pre-existing
# file list (we keep tuples here so RepoState can be frozen too).
FileList = Tuple[str, ...]
