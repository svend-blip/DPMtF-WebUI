"""Coverage-assisted impact index for the test-impact subsystem.

Stores the *observation* made by a broad or full regression run:

    symbol -> set of test paths that actually executed the symbol

The record is bound to the precise repository and policy state at the
moment it was collected. A record from a different state is treated as
incompatible and **discarded** — not trusted, never partially applied.
This is the same fail-closed rule Run 005 applies to evidence staleness:
*unknown compatibility is incompatibility*.

Public API
----------
``__all__ = ["CoverageRecord", "COVERAGE_RECORD_SCHEMA_VERSION", "CoverageError"]``

Design contract
---------------
- ``CoverageRecord`` is a frozen dataclass. It is immutable after
  construction. Mutation would defeat the compatibility guarantee.
- ``merge()`` returns a **new** record; the originals are never mutated.
- ``is_compatible(repo_fp, policy_fp)`` answers the staleness question
  explicitly. An empty fingerprint on either side means *unknown* and
  the record is rejected.
- Coverage is **supporting evidence only** — ``scripts/testing/test_index.py``
  consults it after the static scope is resolved and unions additional
  tests into the selection. It never removes tests and never authorises
  a narrowing the static rules refuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Set

__all__ = ["CoverageRecord", "COVERAGE_RECORD_SCHEMA_VERSION", "CoverageError"]


COVERAGE_RECORD_SCHEMA_VERSION: str = "1"


class CoverageError(Exception):
    """Raised for malformed coverage records or impossible merges."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a Z suffix.

    Used as a default timestamp; the format is stable and sortable.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_symbol_to_tests(
    value: Any,
    *,
    source: str = "CoverageRecord",
) -> Dict[str, Set[str]]:
    """Validate and copy an incoming ``symbol_to_tests`` mapping.

    Returns a new dict where every value is a fresh ``set`` of strings.
    Raises :class:`CoverageError` when the value is the wrong shape.

    Parameters
    ----------
    value:
        The candidate mapping. Must be a ``dict[str, Iterable[str]]``.
    source:
        Diagnostic label embedded in the error message.
    """
    if not isinstance(value, dict):
        raise CoverageError(
            f"{source}.symbol_to_tests must be a dict, "
            f"got {type(value).__name__}"
        )
    out: Dict[str, Set[str]] = {}
    for sym, tests in value.items():
        if not isinstance(sym, str):
            raise CoverageError(
                f"{source}.symbol_to_tests keys must be strings, "
                f"got {type(sym).__name__}"
            )
        if not isinstance(tests, (set, frozenset, list, tuple)):
            raise CoverageError(
                f"{source}.symbol_to_tests[{sym!r}] must be iterable of "
                f"strings, got {type(tests).__name__}"
            )
        coerced: Set[str] = set()
        for t in tests:
            if not isinstance(t, str):
                raise CoverageError(
                    f"{source}.symbol_to_tests[{sym!r}] items must be "
                    f"strings, got {type(t).__name__}"
                )
            coerced.add(t)
        if coerced:
            out[sym] = coerced
    return out


def _normalize_scope(scope: Any) -> str:
    """Validate and normalize a ``run_scope`` value.

    Only ``"broad"`` and ``"full"`` are permitted — coverage collection
    is opt-in precisely at these rungs of the scope ladder.
    """
    if scope not in ("broad", "full"):
        raise CoverageError(
            f"CoverageRecord.run_scope must be 'broad' or 'full', got {scope!r}"
        )
    return scope


def _is_blank(value: Any) -> bool:
    """Return True if *value* is ``None`` or the empty string."""
    return value is None or (isinstance(value, str) and not value)


# ---------------------------------------------------------------------------
# CoverageRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageRecord:
    """An observation: ``symbol -> tests that actually executed the symbol``.

    Attributes
    ----------
    symbol_to_tests:
        Maps symbol name to the set of test paths that executed it.
        Frozen dataclass prevents field reassignment; the inner sets
        themselves are copied on construction and on ``merge`` so that
        callers cannot mutate the record through them.
    repo_fingerprint:
        64-character SHA-256 (or similar opaque identifier) of the
        repository state at collection time. Empty string means *unknown*
        — a record whose own fingerprint is unknown is never compatible.
    policy_fingerprint:
        Hash of the policy file state at collection time. Empty string
        means *unknown* — same rule as ``repo_fingerprint``.
    run_scope:
        The scope that was active when this record was collected.
        Only ``"broad"`` and ``"full"`` are valid collection points.
    collected_at:
        ISO-8601 UTC timestamp of collection. Default is the current
        time; tests may supply a fixed value for determinism.
    schema_version:
        Version of the coverage-record schema. Bumped when the on-disk
        or wire format changes.
    """

    symbol_to_tests: Dict[str, Set[str]] = field(default_factory=dict)
    repo_fingerprint: str = ""
    policy_fingerprint: str = ""
    run_scope: str = "broad"
    collected_at: str = field(default_factory=_utc_now_iso)
    schema_version: str = COVERAGE_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        # ``frozen=True`` blocks attribute assignment, but it does not stop
        # the constructor from accepting mutable values that are then
        # stored as-is. ``object.__setattr__`` is the documented seam for
        # legitimate frozen-dataclass post-construction work; we use it
        # here to replace the inbound mapping with a defensive copy.
        normalized = _coerce_symbol_to_tests(
            self.symbol_to_tests, source="CoverageRecord"
        )
        object.__setattr__(self, "symbol_to_tests", normalized)

        if not isinstance(self.repo_fingerprint, str):
            raise CoverageError(
                f"CoverageRecord.repo_fingerprint must be str, "
                f"got {type(self.repo_fingerprint).__name__}"
            )
        if not isinstance(self.policy_fingerprint, str):
            raise CoverageError(
                f"CoverageRecord.policy_fingerprint must be str, "
                f"got {type(self.policy_fingerprint).__name__}"
            )
        if not isinstance(self.collected_at, str):
            raise CoverageError(
                f"CoverageRecord.collected_at must be str, "
                f"got {type(self.collected_at).__name__}"
            )
        if not isinstance(self.schema_version, str):
            raise CoverageError(
                f"CoverageRecord.schema_version must be str, "
                f"got {type(self.schema_version).__name__}"
            )

        object.__setattr__(self, "run_scope", _normalize_scope(self.run_scope))

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls) -> "CoverageRecord":
        """Return an empty record with unknown fingerprints.

        An empty record is never compatible with any state, so handing it
        to ``tests_for`` is equivalent to handing ``None`` — the static
        selection is unchanged.
        """
        return cls(
            symbol_to_tests={},
            repo_fingerprint="",
            policy_fingerprint="",
            run_scope="broad",
            collected_at="1970-01-01T00:00:00Z",
        )

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    def is_compatible(self, repo_fp: str, policy_fp: str) -> bool:
        """Return ``True`` iff this record matches the supplied state.

        The rule is **strict**: every fingerprint on both sides must be
        a non-empty string, and they must compare equal. An unknown
        fingerprint on any side is **incompatible** — *unknown
        compatibility is incompatibility*, the same fail-closed rule
        Run 005 applies to evidence staleness.
        """
        if _is_blank(self.repo_fingerprint):
            return False
        if _is_blank(self.policy_fingerprint):
            return False
        if _is_blank(repo_fp):
            return False
        if _is_blank(policy_fp):
            return False
        return (
            self.repo_fingerprint == repo_fp
            and self.policy_fingerprint == policy_fp
        )

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge(self, other: "CoverageRecord") -> "CoverageRecord":
        """Return a new record with union-merged ``symbol->tests``.

        Only adds tests; never removes. The merged record inherits the
        fingerprints and ``run_scope`` of ``self`` (the caller is
        responsible for ensuring both records are compatible — this
        method does not silently discard).

        The ``collected_at`` field is set to the lexicographically
        greater of the two timestamps, which is also the chronologically
        later one when both are ISO-8601 UTC strings of the same shape.
        """
        if not isinstance(other, CoverageRecord):
            raise CoverageError(
                f"CoverageRecord.merge expects CoverageRecord, "
                f"got {type(other).__name__}"
            )

        merged_symbols: Dict[str, Set[str]] = {}
        all_symbols = set(self.symbol_to_tests) | set(other.symbol_to_tests)
        for sym in all_symbols:
            s: Set[str] = set()
            if sym in self.symbol_to_tests:
                s |= self.symbol_to_tests[sym]
            if sym in other.symbol_to_tests:
                s |= other.symbol_to_tests[sym]
            if s:
                merged_symbols[sym] = s

        latest_collected_at = self.collected_at
        if other.collected_at > self.collected_at:
            latest_collected_at = other.collected_at

        return CoverageRecord(
            symbol_to_tests=merged_symbols,
            repo_fingerprint=self.repo_fingerprint,
            policy_fingerprint=self.policy_fingerprint,
            run_scope=self.run_scope,
            collected_at=latest_collected_at,
            schema_version=self.schema_version,
        )

    # ------------------------------------------------------------------
    # Derived views
    # ------------------------------------------------------------------

    def all_observed_tests(self) -> Set[str]:
        """Return the union of every test path observed across all symbols.

        Useful for the test-index merger: ``tests_for`` union-merges this
        set into the static selection.
        """
        out: Set[str] = set()
        for tests in self.symbol_to_tests.values():
            out |= tests
        return out

    def is_empty(self) -> bool:
        """Return ``True`` iff no symbols and no tests were observed."""
        return len(self.symbol_to_tests) == 0

    # ------------------------------------------------------------------
    # Serialization (best-effort, deterministic)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable snapshot of this record."""
        return {
            "schema_version": self.schema_version,
            "repo_fingerprint": self.repo_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "run_scope": self.run_scope,
            "collected_at": self.collected_at,
            "symbol_to_tests": {
                sym: sorted(tests)
                for sym, tests in sorted(self.symbol_to_tests.items())
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoverageRecord":
        """Build a record from a dict produced by :meth:`to_dict`.

        Raises :class:`CoverageError` on shape errors.
        """
        if not isinstance(data, dict):
            raise CoverageError(
                f"CoverageRecord.from_dict expects a dict, "
                f"got {type(data).__name__}"
            )
        return cls(
            symbol_to_tests=data.get("symbol_to_tests", {}),
            repo_fingerprint=data.get("repo_fingerprint", ""),
            policy_fingerprint=data.get("policy_fingerprint", ""),
            run_scope=data.get("run_scope", "broad"),
            collected_at=data.get("collected_at", _utc_now_iso()),
            schema_version=data.get(
                "schema_version", COVERAGE_RECORD_SCHEMA_VERSION
            ),
        )
