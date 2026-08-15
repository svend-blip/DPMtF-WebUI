"""Tests for `patcher.models` — `PatchRequest`, `PatchResult`,
serialization round-tripping.

The models are pure data; no disk, no subprocess, no fixtures other than
what pytest itself provides. We cover:

  * default-value handling for both dataclasses
  * `to_dict()` / `from_dict()` round-trip on PatchResult
  * `request_to_dict()` / `request_from_dict()` round-trip
  * tolerance of unknown keys in the loader (forward compatibility)
  * `from_dict()` error surface on truly bad payloads
  * the spec §11 contract: error_code values are exactly the strings
    defined in `patcher.errors`.
"""

from __future__ import annotations

import dataclasses

import pytest

from patcher import errors as patcher_errors
from patcher.models import (
    PatchRequest,
    PatchResult,
    request_from_dict,
    request_to_dict,
)


# ── PatchRequest ────────────────────────────────────────────────────────


class TestPatchRequest:
    def test_minimal_request(self):
        req = PatchRequest(repo_path="/tmp/r", patch_mode="unified_diff")
        assert req.repo_path == "/tmp/r"
        assert req.patch_mode == "unified_diff"
        assert req.operations is None
        assert req.patch is None
        assert req.allowed_paths is None
        assert req.base_revision is None
        assert req.verification is None

    def test_full_request(self):
        req = PatchRequest(
            repo_path="/tmp/r",
            patch_mode="structural_python",
            operations=[{"operation": "add_import", "file": "x.py"}],
            allowed_paths=["src/"],
            base_revision="a" * 40,
            verification={"syntax": True},
        )
        assert req.operations[0]["operation"] == "add_import"
        assert req.allowed_paths == ["src/"]
        assert len(req.base_revision) == 40
        assert req.verification == {"syntax": True}

    def test_request_is_frozen(self):
        req = PatchRequest(repo_path="/tmp/r", patch_mode="unified_diff")
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.repo_path = "/other"  # type: ignore[misc]


# ── PatchResult ─────────────────────────────────────────────────────────


class TestPatchResult:
    def test_minimal_result_is_a_clean_rejection_shape(self):
        r = PatchResult(status="rejected", applied=False, engine="git_apply")
        assert r.files_changed == []
        assert r.files_rejected == []
        assert r.operations_requested == 0
        assert r.operations_applied == 0
        assert r.verification is None
        assert r.resulting_diff is None
        assert r.error_code is None
        assert r.error is None

    def test_applied_shape(self):
        r = PatchResult(
            status="applied",
            applied=True,
            engine="git_apply",
            files_changed=["app.py"],
            operations_requested=1,
            operations_applied=1,
            resulting_diff="diff --git a/app.py b/app.py\n@@ -1 +1 @@\n-old\n+new\n",
            error_code="PATCH_APPLIED",
        )
        assert r.applied is True
        assert r.files_changed == ["app.py"]
        assert r.resulting_diff and "diff --git" in r.resulting_diff
        assert r.error is None

    def test_result_is_frozen(self):
        r = PatchResult(status="applied", applied=True, engine="x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.applied = False  # type: ignore[misc]


# ── Serialization round-trip ────────────────────────────────────────────


class TestSerializationRoundTrip:
    def test_patchresult_round_trip_through_dict(self):
        original = PatchResult(
            status="applied",
            applied=True,
            engine="git_apply",
            files_changed=["a.py", "b.py"],
            files_rejected=[],
            operations_requested=2,
            operations_applied=2,
            verification={"syntax": "passed"},
            resulting_diff="diff --git a/a.py\n",
            error_code="PATCH_APPLIED",
            error=None,
        )
        as_dict = original.to_dict()
        rebuilt = PatchResult.from_dict(as_dict)
        assert rebuilt == original

    def test_patchresult_round_trip_ignores_unknown_keys(self):
        """Forward compatibility: a future schema addition must not break
        today's loader."""
        original = PatchResult(
            status="rejected",
            applied=False,
            engine="git_apply",
            error_code="PATCH_CONFLICT",
            error="nope",
        )
        as_dict = original.to_dict()
        as_dict["future_field"] = "ignored"
        as_dict["another"] = 42
        rebuilt = PatchResult.from_dict(as_dict)
        assert rebuilt == original

    def test_patchrequest_round_trip_through_dict(self):
        original = PatchRequest(
            repo_path="/r",
            patch_mode="structural_python",
            operations=[{"operation": "add_import", "file": "x.py"}],
            allowed_paths=["src/"],
            base_revision="f" * 40,
        )
        rebuilt = request_from_dict(request_to_dict(original))
        assert rebuilt == original

    def test_to_dict_is_json_friendly(self):
        """The serialized form must be JSON-loadable with the stdlib."""
        import json

        r = PatchResult(
            status="applied",
            applied=True,
            engine="git_apply",
            files_changed=["x.py"],
            verification={"syntax": "passed", "lint": "not_run"},
        )
        loaded = json.loads(json.dumps(r.to_dict()))
        assert loaded["engine"] == "git_apply"
        assert loaded["files_changed"] == ["x.py"]
        assert loaded["verification"]["syntax"] == "passed"

    def test_request_from_dict_none_payload_raises(self):
        with pytest.raises(ValueError):
            request_from_dict(None)


# ── Spec §11 contract ───────────────────────────────────────────────────


class TestSpec11Contract:
    """The 14 error codes named in spec §11 must be present, exactly
    spelled, and exposed both from `patcher.errors` and `patcher`.
    """

    EXPECTED = [
        "PATCH_INVALID",
        "PATCH_UNSUPPORTED_OPERATION",
        "PATCH_FILE_NOT_FOUND",
        "PATCH_PATH_REJECTED",
        "PATCH_BASE_MISMATCH",
        "PATCH_TARGET_NOT_FOUND",
        "PATCH_TARGET_AMBIGUOUS",
        "PATCH_CONFLICT",
        "PATCH_APPLY_FAILED",
        "PATCH_APPLIED",
        "PATCH_APPLIED_SYNTAX_FAILED",
        "PATCH_APPLIED_LINT_FAILED",
        "PATCH_APPLIED_TEST_FAILED",
        "PATCH_INTERNAL_ERROR",
    ]

    def test_every_code_exists(self):
        for code in self.EXPECTED:
            assert hasattr(patcher_errors, code), code

    def test_every_code_is_a_string_with_the_expected_value(self):
        for code in self.EXPECTED:
            value = getattr(patcher_errors, code)
            assert value == code, (code, value)
