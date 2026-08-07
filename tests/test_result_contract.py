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

    Nothing caught it because no result had ever carried content. The path was
    wrong from the first execution and correct-looking in every log.
    """

    def test_the_implementer_produces_a_result_not_a_handoff(self):
        from worker_routing import outgoing_deliverable
        path = outgoing_deliverable("lightworker", "imple01LW", "007")
        assert path == "lightworker/results/007-result.md"
        assert "handoffs" not in path

    def test_the_reviewer_produces_a_verdict(self):
        from worker_routing import outgoing_deliverable
        assert outgoing_deliverable("lightworker", "review01LW", "007") == \
            "lightworker/verdicts/007-verdict.md"

    def test_a_role_with_nowhere_to_put_a_result_raises(self):
        """Inventing a path would put the deliverable somewhere nobody reads,
        which is worse than refusing to dispatch."""
        from worker_routing import EnvelopeIncomplete, outgoing_deliverable
        with pytest.raises(EnvelopeIncomplete):
            outgoing_deliverable("lightworker", "no-such-role", "007")
