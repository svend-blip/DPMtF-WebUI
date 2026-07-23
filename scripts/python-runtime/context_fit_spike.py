#!/usr/bin/env python3
"""Handoff context-fit spike (Task 4.4).

Question: Can DPMtF determine whether a handoff is safely executable
by the selected local model before queueing it?

Model Allocator supplies:
- effective context window
- recommended input limit
- output reserve
- backend capability
- model availability

DPMtF evaluates:
- estimated initial context
- expected peak context
- governance overhead
- required file context
- expected tool output
- output reserve
- recovery reserve
- likely changed-file count
- architectural spread
- verification scope
"""
from dataclasses import dataclass, field
from typing import Optional
import json
import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Fit states ───────────────────────────────────────────────────

FIT_STATES = [
    "FITS",
    "FITS_WITH_LOW_MARGIN",
    "CONTEXT_REDUCTION_REQUIRED",
    "SPLIT_REQUIRED",
    "LARGER_MODEL_REQUIRED",
    "HUMAN_REDESIGN_REQUIRED",
]

# Only these states may enter the executable queue
EXECUTABLE_STATES = {"FITS", "FITS_WITH_LOW_MARGIN"}


# ── Context budget estimation ───────────────────────────────────

@dataclass
class ContextBudget:
    """Estimated context usage for a handoff."""
    # Input context (tokens)
    system_instruction: int = 500
    governance_overhead: int = 0
    handoff_prompt: int = 0
    required_file_context: int = 0
    knowledge_fragments: int = 0
    previous_checkpoint: int = 0
    
    # Expected growth during execution (tokens)
    expected_tool_output: int = 0
    expected_model_reasoning: int = 0
    
    # Reserves (tokens)
    output_reserve: int = 8192
    recovery_reserve: int = 4096
    
    # Model limits (tokens)
    model_context_window: int = 0
    recommended_input_limit: int = 0
    
    @property
    def estimated_initial(self) -> int:
        return (self.system_instruction + self.governance_overhead +
                self.handoff_prompt + self.required_file_context +
                self.knowledge_fragments + self.previous_checkpoint)
    
    @property
    def estimated_peak(self) -> int:
        return self.estimated_initial + self.expected_tool_output + self.expected_model_reasoning
    
    @property
    def total_with_reserves(self) -> int:
        return self.estimated_peak + self.output_reserve + self.recovery_reserve
    
    @property
    def margin(self) -> int:
        if self.model_context_window == 0:
            return -1
        return self.model_context_window - self.total_with_reserves
    
    @property
    def margin_percent(self) -> float:
        if self.model_context_window == 0:
            return -1.0
        return (self.margin / self.model_context_window) * 100


# ── Handoff characteristics ──────────────────────────────────────

@dataclass
class HandoffCharacteristics:
    """What DPMtF knows about a handoff before execution."""
    goal_text: str = ""
    changed_file_count: int = 1
    architectural_spread: int = 1  # 1=single file, 5=multi-module
    verification_scope: int = 1  # 1=py_compile only, 5=full test suite
    governance_files_count: int = 1
    requires_file_reads: int = 0  # how many files to READ_FILE
    estimated_lines_per_file: int = 50


def estimate_file_context(ch: HandoffCharacteristics) -> int:
    """Estimate tokens needed for file context."""
    # Rough: 1 token ≈ 4 chars, average line ≈ 40 chars
    chars_per_file = ch.estimated_lines_per_file * 40
    tokens_per_file = chars_per_file // 4
    return ch.requires_file_reads * tokens_per_file


def estimate_governance_overhead(ch: HandoffCharacteristics) -> int:
    """Estimate tokens for governance file references."""
    # Average governance file ≈ 2000 tokens
    return ch.governance_files_count * 2000


def estimate_tool_output(ch: HandoffCharacteristics) -> int:
    """Estimate tokens for tool output during execution."""
    # READ_FILE outputs + verification output
    read_output = ch.requires_file_reads * ch.estimated_lines_per_file * 10
    verification_output = ch.verification_scope * 500
    return read_output + verification_output


def estimate_model_reasoning(ch: HandoffCharacteristics) -> int:
    """Estimate tokens for model reasoning/thinking."""
    # More complex tasks = more reasoning
    base = 1000
    complexity_multiplier = ch.architectural_spread * ch.changed_file_count
    return base + (complexity_multiplier * 500)


# ── Fit evaluation ───────────────────────────────────────────────

def evaluate_fit(
    ch: HandoffCharacteristics,
    model_context_window: int,
    recommended_input_limit: int = 0,
    output_reserve: int = 8192,
    recovery_reserve: int = 4096,
) -> tuple[str, ContextBudget]:
    """Evaluate whether a handoff fits the model's context budget.
    
    Returns (fit_state, budget).
    """
    if recommended_input_limit == 0:
        recommended_input_limit = int(model_context_window * 0.75)
    
    budget = ContextBudget(
        governance_overhead=estimate_governance_overhead(ch),
        handoff_prompt=len(ch.goal_text) // 4,
        required_file_context=estimate_file_context(ch),
        expected_tool_output=estimate_tool_output(ch),
        expected_model_reasoning=estimate_model_reasoning(ch),
        output_reserve=output_reserve,
        recovery_reserve=recovery_reserve,
        model_context_window=model_context_window,
        recommended_input_limit=recommended_input_limit,
    )
    
    # Decision tree
    if budget.total_with_reserves > model_context_window:
        # Exceeds total context window
        over_ratio = budget.total_with_reserves / model_context_window
        if over_ratio > 2.0:
            return "SPLIT_REQUIRED", budget
        elif over_ratio > 1.5:
            return "LARGER_MODEL_REQUIRED", budget
        else:
            return "CONTEXT_REDUCTION_REQUIRED", budget
    
    if budget.estimated_initial > recommended_input_limit:
        # Exceeds recommended input limit (75% of context)
        return "CONTEXT_REDUCTION_REQUIRED", budget
    
    margin_pct = budget.margin_percent
    if margin_pct < 0:
        return "CONTEXT_REDUCTION_REQUIRED", budget
    elif margin_pct < 10:
        return "FITS_WITH_LOW_MARGIN", budget
    else:
        return "FITS", budget


def is_executable(fit_state: str) -> bool:
    """Only approved fit states may enter the executable queue."""
    return fit_state in EXECUTABLE_STATES


# ── Continuation creation (split) ────────────────────────────────

@dataclass
class ContinuationPlan:
    """Plan for splitting an oversized handoff into continuations."""
    original_goal: str = ""
    continuations: list[HandoffCharacteristics] = field(default_factory=list)
    reason: str = ""


def create_continuation(ch: HandoffCharacteristics, model_context_window: int) -> Optional[ContinuationPlan]:
    """If a handoff is too large, create a continuation plan.
    
    Splits by reducing changed_file_count and architectural_spread
    until each continuation fits.
    """
    fit_state, budget = evaluate_fit(ch, model_context_window)
    
    if fit_state in EXECUTABLE_STATES:
        return None  # No split needed
    
    if fit_state == "HUMAN_REDESIGN_REQUIRED":
        return ContinuationPlan(
            original_goal=ch.goal_text,
            reason="Handoff is too complex for any single model — human redesign required"
        )
    
    plan = ContinuationPlan(original_goal=ch.goal_text, reason=fit_state)
    
    # Simple split: divide changed files into chunks that fit
    files_per_chunk = max(1, ch.changed_file_count // 2)
    remaining = ch.changed_file_count
    
    while remaining > 0:
        chunk = min(files_per_chunk, remaining)
        sub = HandoffCharacteristics(
            goal_text=f"(continuation — {chunk} of {ch.changed_file_count} files)",
            changed_file_count=chunk,
            architectural_spread=min(ch.architectural_spread, 2),
            verification_scope=ch.verification_scope,
            governance_files_count=ch.governance_files_count,
            requires_file_reads=chunk,
            estimated_lines_per_file=ch.estimated_lines_per_file,
        )
        sub_fit, _ = evaluate_fit(sub, model_context_window)
        if sub_fit in EXECUTABLE_STATES:
            plan.continuations.append(sub)
            remaining -= chunk
        else:
            # Reduce further
            files_per_chunk = max(1, files_per_chunk // 2)
            if files_per_chunk == 1 and sub_fit not in EXECUTABLE_STATES:
                plan.reason = "LARGER_MODEL_REQUIRED"
                plan.continuations.append(sub)
                remaining -= chunk
    
    return plan


# ── Resolve model context via allocator ──────────────────────────

def resolve_model_context(role: str, client: str) -> dict:
    """Resolve model context window via Model Allocator."""
    import config
    allocator_path = os.path.join(
        config.get_project_path("model-allocator"), "scripts", "model-allocator"
    )
    result = subprocess.run(
        [allocator_path, "validate", "--alias", role, "--client", client, "--json"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode not in (0, 2):  # 0=OK, 2=WARNING
        return {"context": 131072, "backend": "unknown", "real_model": "unknown"}
    data = json.loads(result.stdout)
    return {
        "context": data.get("resolved_context", 131072),
        "backend": data.get("resolved_backend", "unknown"),
        "real_model": data.get("resolved_real_model", "unknown"),
    }
