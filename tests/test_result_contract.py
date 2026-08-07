"""Father's two result validators must agree, and the worker must satisfy both.

Every failure in lightworker run 001 was the same shape: two components, each
correct on its own, disagreeing about something neither had written down. The
envelope's nesting, the temp file's existence, the permission block's origin,
and finally this one -- Father holding two different ideas of what a result is.

`routers/lightworkers.py` guards the endpoint. `scripts/bridgeV002/worker_results.py`
guards the return path that publishes the deliverable and advances the chain. A
result can pass the first and be refused by the second, which is what EXEC-005
did: 422 from a completion the store had already recorded.

These tests are cheap on purpose. Each disagreement above cost a dispatch to
the worker to discover -- five minutes and a model start. This costs a second,
and catches the same class.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

from routers.lightworkers import _validate_result  # noqa: E402
from worker_results import ResultRejected, validate_result  # noqa: E402


CONTENT = "# Repository at the base commit\n\nThree facts follow.\n"


def a_good_result():
    """The result a worker returns for `deliverable_only`.

    This literal is the contract. Both validators are asserted against it, so
    changing one side without the other turns a test red here rather than
    turning up as a 422 on a live execution.
    """
    return {
        "status": "role_execution_completed",
        "result_mode": "deliverable_only",
        "deliverable": {
            "path": "lightworker/results/001-result.md",
            "content": CONTENT,
            "sha256": hashlib.sha256(CONTENT.encode("utf-8")).hexdigest(),
        },
    }


def test_the_endpoint_accepts_the_contract_result():
    assert _validate_result(a_good_result()) is None


def test_the_return_path_accepts_the_contract_result():
    assert validate_result(a_good_result()) == CONTENT


def test_what_the_endpoint_accepts_the_return_path_also_accepts():
    """The property that actually failed. A result the endpoint waves through
    and the return path refuses becomes a 422 on a completion the store has
    already recorded -- and the worker cannot even report the failure, because
    the execution is terminal by then."""
    result = a_good_result()
    assert _validate_result(result) is None
    validate_result(result)  # must not raise


def test_a_result_without_content_is_refused_by_both():
    """EXEC-005 exactly: the worker reported a path and an empty checksum. The
    endpoint let it through and the return path refused it."""
    result = a_good_result()
    del result["deliverable"]["content"]
    assert _validate_result(result) is not None
    with pytest.raises(ResultRejected):
        validate_result(result)


def test_a_mismatched_checksum_is_refused_by_the_return_path_alone():
    """Deliberately not checked at the endpoint. §23 makes the checksum
    Father's authoritative validation, and duplicating it in two places is
    precisely how the two validators drifted apart. The endpoint's job is
    shape; the return path decides whether the content is what it claims."""
    result = a_good_result()
    result["deliverable"]["sha256"] = "0" * 64
    with pytest.raises(ResultRejected):
        validate_result(result)
    assert _validate_result(result) is None


def test_the_two_validators_use_the_same_field_names():
    """Named separately because the failure was a vocabulary mismatch, not a
    logic error: `mode` against `result_mode`, a path string against an object.
    A test that only exercised a good result would pass on either vocabulary
    as long as both sides happened to share it."""
    result = a_good_result()
    assert "result_mode" in result and "mode" not in result
    assert isinstance(result["deliverable"], dict)
    assert _validate_result(result) is None
    validate_result(result)


# ---------------------------------------------------------------------------
# Where the result belongs
# ---------------------------------------------------------------------------


class TestTheEnvelopeNamesWhatTheRoleProduces:
    """A role's deliverable sits on the step it *sends*, not the one that
    delivers to it.

    The envelope used to carry the incoming step's deliverable, which is the
    handoff. Father's return path writes an accepted result to whatever the
    envelope names, so the first result to carry content would have
    overwritten the handoff that produced it -- and a reviewer re-running the
    implementer's commands would have found the task replaced by its answer.

    Measured against a fixture database, not the live one. An earlier
    version of these tests read `databases/dpmtf.db` directly, which made
    the suite red whenever the live flow rows changed -- a test that fails
    on production state is measuring operations, not code.
    """

    @pytest.fixture
    def flow_db(self, tmp_path, monkeypatch):
        import sqlite3

        import config as father_config

        db = tmp_path / "flows.db"
        conn = sqlite3.connect(db)
        conn.executescript(
            "CREATE TABLE bridge_flow_steps ("
            " flow_key TEXT, step_key TEXT, from_role TEXT, to_role TEXT,"
            " deliverable_dir TEXT, deliverable_pattern TEXT,"
            " sort_order INTEGER, is_active INTEGER)"
        )
        conn.executemany(
            "INSERT INTO bridge_flow_steps VALUES (?,?,?,?,?,?,?,1)",
            [
                ("lw", "human-imple", "human", "imple",
                 "lw/handoffs", "{ID}-handoff.md", 0),
                ("lw", "imple-review", "imple", "review",
                 "lw/results", "{ID}-result.md", 1),
                ("lw", "review-human", "review", "human",
                 "lw/verdicts", "{ID}-verdict.md", 2),
            ],
        )
        conn.commit()
        conn.close()
        # outgoing_deliverable imports `config` lazily; the module object in
        # sys.modules is the one patched here, so the lazy import sees it.
        monkeypatch.setattr(father_config, "get_db_path", lambda: str(db))
        return db

    def test_the_implementer_produces_a_result_not_a_handoff(self, flow_db):
        from worker_routing import outgoing_deliverable
        path = outgoing_deliverable("lw", "imple", "007")
        assert path == "lw/results/007-result.md"
        assert "handoffs" not in path

    def test_the_reviewer_produces_a_verdict(self, flow_db):
        from worker_routing import outgoing_deliverable
        assert outgoing_deliverable("lw", "review", "007") == \
            "lw/verdicts/007-verdict.md"

    def test_a_role_with_nowhere_to_put_a_result_raises(self, flow_db):
        """Inventing a path would put the deliverable somewhere nobody reads,
        which is worse than refusing to dispatch."""
        from worker_routing import EnvelopeIncomplete, outgoing_deliverable
        with pytest.raises(EnvelopeIncomplete):
            outgoing_deliverable("lw", "no-such-role", "007")


# ---------------------------------------------------------------------------
# The property, not the instance
# ---------------------------------------------------------------------------


def test_whatever_the_return_path_refuses_the_endpoint_also_refuses():
    """The class-level guarantee the single-literal tests cannot give.

    The `mode`/`result_mode` split was fixed by holding both validators to
    one good literal -- and the same disagreement survived in `status`,
    because the literal happened to carry it. A result the endpoint accepts
    and the return path refuses is recorded as completed, never advances the
    chain, writes no file and raises no alarm.

    So: remove each field of a good result in turn. Wherever the return path
    refuses the mutilated result, the endpoint must refuse it too --
    refusal must happen BEFORE the store records a completion.
    """
    for key in list(a_good_result().keys()):
        broken = a_good_result()
        del broken[key]
        try:
            validate_result(broken)
            return_path_refuses = False
        except ResultRejected:
            return_path_refuses = True
        if return_path_refuses:
            assert _validate_result(broken) is not None, (
                f"the return path refuses a result missing {key!r}; "
                "the endpoint accepts it and records a completion"
            )


def test_the_two_status_constants_are_the_same_string():
    """The endpoint restates the return path's ACCEPTED_STATUS because the
    router must import without the bridge scripts on sys.path. Restated
    means it can drift; this pins it."""
    from routers.lightworkers import _REQUIRED_STATUS
    from worker_results import ACCEPTED_STATUS
    assert _REQUIRED_STATUS == ACCEPTED_STATUS


def test_a_result_without_status_is_refused_by_both():
    """The field the property test was written to catch, named explicitly."""
    result = a_good_result()
    del result["status"]
    assert _validate_result(result) is not None
    with pytest.raises(ResultRejected):
        validate_result(result)


class TestArtifactReferences:
    """§23's artifact_reference: content too large for the result JSON is
    uploaded content-addressed, and the result carries only its sha256.

    The reference is redeemed with the same stance §23 takes on results:
    Father verifies rather than trusts -- the filename promises the hash,
    and the promise is still checked, because a filesystem is writable by
    more than this code path.
    """

    @pytest.fixture
    def artifact(self, tmp_path, monkeypatch):
        import hashlib as hl

        import worker_results as wr
        adir = tmp_path / "artifacts"
        adir.mkdir()
        monkeypatch.setattr(wr, "_artifacts_dir", lambda: str(adir))
        data = ("x" * 1000 + "\n").encode()
        sha = hl.sha256(data).hexdigest()
        (adir / sha).write_bytes(data)
        return sha, data, adir

    def _ref_result(self, sha):
        r = a_good_result()
        del r["deliverable"]["content"]
        r["deliverable"]["artifact_sha256"] = sha
        r["deliverable"]["sha256"] = sha
        return r

    def test_a_reference_redeems_to_its_content(self, artifact):
        sha, data, _ = artifact
        assert validate_result(self._ref_result(sha)) == data.decode()

    def test_a_never_uploaded_reference_is_refused(self, artifact):
        sha, _, _ = artifact
        missing = "0" * 64
        with pytest.raises(ResultRejected) as e:
            validate_result(self._ref_result(missing))
        assert "never uploaded" in str(e.value)

    def test_a_tampered_artifact_is_refused(self, artifact):
        """The name IS the integrity promise; a file that no longer hashes
        to its own name is not the artifact the result referenced."""
        sha, _, adir = artifact
        (adir / sha).write_bytes(b"tampered")
        with pytest.raises(ResultRejected) as e:
            validate_result(self._ref_result(sha))
        assert "does not hash to its own name" in str(e.value)

    def test_the_endpoint_accepts_the_reference_form_too(self, artifact):
        """The property test's guarantee must hold for this shape as well:
        what the return path accepts, the endpoint must not refuse."""
        sha, _, _ = artifact
        assert _validate_result(self._ref_result(sha)) is None
