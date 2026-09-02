"""start_coding threads an alias's reasoning_effort to simple-harness (2026-09-02).

The launch env block sits inside the native-launch branch, which needs a
live allocator and DB to exercise; this test pins the wiring at source
level the way test_launchspec_literals pins its literals: the env name
simple-harness reads, fed from the resolved alias, next to the output cap.
"""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "scripts" / "bridgeV002" / "start_coding.py").read_text()


def test_reasoning_effort_env_is_wired_from_the_resolved_alias():
    assert 'child_env["SIMPLE_HARNESS_REASONING_EFFORT"] = str(reasoning_effort)' in SRC
    assert 'reasoning_effort = resolved.get("reasoning_effort")' in SRC


def test_reasoning_effort_is_only_set_when_present():
    block = SRC[SRC.index('reasoning_effort = resolved.get("reasoning_effort")'):]
    block = block[: block.index('child_env["SIMPLE_HARNESS_REASONING_EFFORT"]')]
    assert "if reasoning_effort:" in block


def test_reasoning_effort_follows_the_output_cap_block():
    assert SRC.index('SIMPLE_HARNESS_MAX_OUTPUT_TOKENS') < SRC.index('SIMPLE_HARNESS_REASONING_EFFORT')


def test_thinking_controls_are_wired_from_the_resolved_alias():
    assert 'enable_thinking = resolved.get("enable_thinking")' in SRC
    assert 'child_env["SIMPLE_HARNESS_ENABLE_THINKING"] = "true" if enable_thinking else "false"' in SRC
    assert 'child_env["SIMPLE_HARNESS_THINKING_BUDGET"] = str(thinking_budget)' in SRC
    block = SRC[SRC.index('enable_thinking = resolved.get("enable_thinking")'):]
    assert "if enable_thinking is not None:" in block[: block.index("SIMPLE_HARNESS_ENABLE_THINKING")]
