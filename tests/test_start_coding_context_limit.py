"""A BridgeV002 simple-harness role runs bounded by its model's context window.

simple-harness bounds a run (pruning, compaction) only when it knows the
model's window. It asks the runtime, and a local runtime usually answers; a
cloud API's /v1/models names the model and nothing else, so against one the
limit stays unknown and the lifecycle accounts without bounding. The allocator
already carries `context` for every alias; the launch never passed it on, so
the cloud roles — the ones whose tokens cost money — ran unbounded.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import start_coding  # noqa: E402

SRC = (PROJECT_ROOT / "scripts" / "bridgeV002" / "start_coding.py").read_text()
NAME = "SIMPLE_HARNESS_CONTEXT_MODEL_LIMIT"


def test_the_aliass_context_becomes_the_configured_limit():
    assert start_coding.context_limit_env({"context": 131072}) == {NAME: "131072"}
    # the allocator's JSON may carry it as a string
    assert start_coding.context_limit_env({"context": "65536"}) == {NAME: "65536"}


def test_what_the_alias_does_not_say_is_not_set():
    for resolved in ({}, {"context": None}, {"context": 0}, {"context": -1},
                     {"context": "plenty"}, {"context": ""}):
        assert start_coding.context_limit_env(resolved) == {}, resolved


def test_it_is_the_configured_limit_not_the_flag():
    # simple-harness reconciles a CONFIGURED limit with what the runtime
    # reports by taking the smaller; --context-limit skips that probe and
    # would override a local runtime serving the model with a smaller window
    # than the alias declares.
    assert "--context-limit" not in SRC


def test_the_launch_block_applies_it_from_the_resolved_alias():
    assert "child_env.update(context_limit_env(resolved))" in SRC
    # beside the other per-alias harness settings, inside the same branch
    assert SRC.index("SIMPLE_HARNESS_MAX_OUTPUT_TOKENS") < SRC.index("child_env.update(context_limit_env(resolved))")
