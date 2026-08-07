"""Tests for the return path (GOAL.md §23, §6.1).

§23's closing line is the whole design: *worker completion is not equivalent
to Father acceptance; Father performs authoritative validation.* So these
tests care less about the happy path than about what Father refuses, and
about the order — validate, then materialise, then advance. A deliverable
written before it is checked is a deliverable a reviewer will trust.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

from worker_results import (  # noqa: E402
    ResultRejected, accept_and_advance, validate_result, write_deliverable)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _result(content="# the deliverable\n", **over):
    r = {
        "status": "role_execution_completed",
        "result_mode": "deliverable_only",
        "deliverable": {"path": "x.md", "content": content, "sha256": _sha(content)},
    }
    r.update(over)
    return r


def _execution(relative="preferred_cloud/results/014-result.md"):
    return {"execution_id": "EXEC-014-IMPLE01", "envelope": {
        "flow_key": "preferred_cloud", "target_role": "imple01",
        "handoff_id": "014", "handoff": {"expected_deliverable": relative}}}


class TestWhatFatherRefuses:

    def test_a_failed_execution_does_not_advance(self):
        with pytest.raises(ResultRejected, match="status"):
            validate_result(_result(status="role_execution_failed"))

    def test_an_unsupported_mode_is_named(self):
        """The message must list what IS accepted -- which since patch mode
        landed (2026-08-07) includes patch_and_deliverable."""
        r = _result()
        r["result_mode"] = "carrier-pigeon"
        with pytest.raises(ResultRejected, match="patch_and_deliverable"):
            validate_result(r)

    def test_a_contentless_deliverable_without_a_reference_is_refused(self):
        """This test used to pin "Father cannot fetch artifacts yet" -- it
        can now (§23 artifact_sha256, 2026-08-07), so what remains refusable
        is a deliverable carrying NEITHER content NOR a reference. The old
        free-form `artifact_reference` string never became a contract; the
        reference IS the sha256."""
        r = _result()
        r["deliverable"] = {"path": "x.md", "artifact_reference": "art://1"}
        with pytest.raises(ResultRejected, match="no artifact_sha256"):
            validate_result(r)

    def test_a_mismatched_checksum_is_refused(self):
        """The worker's own claim about its content is checked, not believed."""
        r = _result()
        r["deliverable"]["sha256"] = _sha("something else entirely")
        with pytest.raises(ResultRejected, match="sha256 mismatch"):
            validate_result(r)

    def test_empty_content_is_refused(self):
        with pytest.raises(ResultRejected, match="empty"):
            validate_result(_result(content="   \n"))

    def test_a_result_with_no_deliverable_block_is_refused(self):
        r = _result()
        del r["deliverable"]
        with pytest.raises(ResultRejected, match="no deliverable"):
            validate_result(r)


class TestNothingIsWrittenUntilItIsAccepted:

    def test_a_rejected_result_leaves_no_file_behind(self, tmp_path):
        calls = []
        with pytest.raises(ResultRejected):
            accept_and_advance(
                execution=_execution(), result=_result(status="role_execution_failed"),
                bridge_dir=str(tmp_path), signal=lambda *a, **k: calls.append(a))
        assert not list(tmp_path.rglob("*.md")), "a refused result was written"
        assert calls == [], "a refused result advanced the chain"

    def test_the_chain_advances_only_after_the_file_exists(self, tmp_path):
        seen = {}

        def signal(flow, _from, role, hid, **kw):
            target = tmp_path / "preferred_cloud/results/014-result.md"
            seen["existed_at_signal"] = target.is_file()
            seen["args"] = (flow, role, hid)

        accept_and_advance(execution=_execution(), result=_result(),
                           bridge_dir=str(tmp_path), signal=signal)
        assert seen["existed_at_signal"], \
            "the next role was signalled before the deliverable existed"
        assert seen["args"] == ("preferred_cloud", "imple01", "014")

    def test_an_offer_without_a_destination_is_refused(self, tmp_path):
        with pytest.raises(ResultRejected, match="expected_deliverable"):
            accept_and_advance(execution=_execution(relative=""), result=_result(),
                               bridge_dir=str(tmp_path), signal=lambda *a, **k: None)


class TestThePublishIsAtomic:

    def test_no_partial_file_survives(self, tmp_path):
        target = tmp_path / "sub" / "out.md"
        write_deliverable("content", str(target))
        assert target.read_text(encoding="utf-8") == "content"
        assert [p.name for p in (tmp_path / "sub").iterdir()] == ["out.md"], \
            "a .partial file was left behind"


class TestTheRouterHookRefusesRatherThanSwallows:

    def test_a_rejection_becomes_422_and_the_completion_stays_recorded(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routers.lightworkers import InMemoryStore, create_router
        import os

        os.environ["LIGHTWORKER_AUTH_TOKEN"] = "t"
        store = InMemoryStore()
        store.offer({"execution_id": "E1", "worker_id": "w1", "target_role": "imple01"})

        def on_complete(execution_id, result):
            raise ResultRejected("Father says no")

        app = FastAPI()
        app.include_router(create_router(store, on_complete=on_complete))
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer t"})
        c.post("/api/lightworkers/executions/E1/claim", json={"worker_id": "w1"})
        r = c.post("/api/lightworkers/executions/E1/complete", json={
            "worker_id": "w1", "attempt_id": "a1",
            "result": {"status": "role_execution_completed",
                       "result_mode": "deliverable_only",
                       "deliverable": {"path": "x", "content": "a doc\n"}}})
        assert r.status_code == 422
        assert "Father says no" in r.text
        assert store.completion_count("E1", "a1") == 1, \
            "the worker's report was discarded; it should stay recorded"
