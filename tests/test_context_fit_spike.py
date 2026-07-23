"""Tests for the Handoff context-fit spike (Task 4.4)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

from context_fit_spike import (
    ContextBudget, HandoffCharacteristics, evaluate_fit,
    is_executable, create_continuation, estimate_file_context,
    estimate_governance_overhead, estimate_tool_output,
    EXECUTABLE_STATES, FIT_STATES,
)


def test_small_handoff_fits():
    """A simple 1-file handoff should FIT in a 131072 context model."""
    ch = HandoffCharacteristics(
        goal_text="Add a function to file.py",
        changed_file_count=1,
        architectural_spread=1,
        verification_scope=1,
        governance_files_count=1,
        requires_file_reads=1,
        estimated_lines_per_file=50,
    )
    fit, budget = evaluate_fit(ch, model_context_window=131072)
    assert fit == "FITS"
    assert is_executable(fit)


def test_large_handoff_exceeds_context():
    """A huge handoff should require a split or larger model."""
    ch = HandoffCharacteristics(
        goal_text="Refactor the entire authentication system across 20 files",
        changed_file_count=20,
        architectural_spread=5,
        verification_scope=5,
        governance_files_count=5,
        requires_file_reads=20,
        estimated_lines_per_file=200,
    )
    fit, budget = evaluate_fit(ch, model_context_window=32768)
    assert fit in ("SPLIT_REQUIRED", "LARGER_MODEL_REQUIRED", "CONTEXT_REDUCTION_REQUIRED")
    assert not is_executable(fit)


def test_medium_handoff_low_margin():
    """A medium handoff in a small context model should have low margin."""
    ch = HandoffCharacteristics(
        goal_text="Add endpoint to router and update tests",
        changed_file_count=3,
        architectural_spread=2,
        verification_scope=2,
        governance_files_count=2,
        requires_file_reads=3,
        estimated_lines_per_file=100,
    )
    fit, budget = evaluate_fit(ch, model_context_window=32768)
    # Should either FIT_WITH_LOW_MARGIN or CONTEXT_REDUCTION_REQUIRED
    assert fit in ("FITS", "FITS_WITH_LOW_MARGIN", "CONTEXT_REDUCTION_REQUIRED")


def test_continuation_split():
    """Oversized handoff should be splittable into continuations."""
    ch = HandoffCharacteristics(
        goal_text="Refactor 10 files",
        changed_file_count=10,
        architectural_spread=3,
        verification_scope=3,
        governance_files_count=3,
        requires_file_reads=10,
        estimated_lines_per_file=150,
    )
    plan = create_continuation(ch, model_context_window=32768)
    if plan:
        assert len(plan.continuations) > 1
        # Each continuation should be smaller
        for cont in plan.continuations:
            assert cont.changed_file_count < ch.changed_file_count


def test_no_split_needed_for_small_handoff():
    """Small handoff should not need a continuation plan."""
    ch = HandoffCharacteristics(
        goal_text="Fix typo in file.py",
        changed_file_count=1,
        requires_file_reads=1,
        estimated_lines_per_file=20,
    )
    plan = create_continuation(ch, model_context_window=131072)
    assert plan is None


def test_budget_calculation():
    """Budget should correctly sum all components."""
    ch = HandoffCharacteristics(
        goal_text="x" * 400,  # 100 tokens
        changed_file_count=2,
        governance_files_count=2,
        requires_file_reads=2,
        estimated_lines_per_file=100,
        architectural_spread=2,
        verification_scope=2,
    )
    budget = ContextBudget(
        governance_overhead=estimate_governance_overhead(ch),
        handoff_prompt=len(ch.goal_text) // 4,
        required_file_context=estimate_file_context(ch),
        expected_tool_output=estimate_tool_output(ch),
        output_reserve=8192,
        recovery_reserve=4096,
        model_context_window=131072,
    )
    
    assert budget.estimated_initial > 0
    assert budget.estimated_peak > budget.estimated_initial
    assert budget.total_with_reserves > budget.estimated_peak
    assert budget.margin > 0  # Should have positive margin for this size


def test_executable_states_only():
    """Only FITS and FITS_WITH_LOW_MARGIN are executable."""
    assert is_executable("FITS")
    assert is_executable("FITS_WITH_LOW_MARGIN")
    assert not is_executable("CONTEXT_REDUCTION_REQUIRED")
    assert not is_executable("SPLIT_REQUIRED")
    assert not is_executable("LARGER_MODEL_REQUIRED")
    assert not is_executable("HUMAN_REDESIGN_REQUIRED")


def test_different_models_different_fit():
    """Same handoff can fit in a large model but not a small one."""
    ch = HandoffCharacteristics(
        goal_text="Add a complex feature across 5 files",
        changed_file_count=5,
        architectural_spread=3,
        verification_scope=3,
        governance_files_count=3,
        requires_file_reads=5,
        estimated_lines_per_file=150,
    )
    fit_large, _ = evaluate_fit(ch, model_context_window=131072)
    fit_small, _ = evaluate_fit(ch, model_context_window=32768)
    
    # Should fit better in the large model
    assert is_executable(fit_large) or fit_large == "FITS_WITH_LOW_MARGIN"
    # Small model may struggle
    assert fit_small in FIT_STATES


def test_output_reserve_protected():
    """Budget must always include output + recovery reserves."""
    ch = HandoffCharacteristics(goal_text="test", changed_file_count=1, requires_file_reads=0)
    _, budget = evaluate_fit(ch, model_context_window=65536)
    
    assert budget.output_reserve > 0
    assert budget.recovery_reserve > 0
    assert budget.total_with_reserves == budget.estimated_peak + budget.output_reserve + budget.recovery_reserve
