"""Handoff Compiler — decomposes approved goals into bounded execution jobs.

Takes a Human-approved goal + flow_key + target_project and produces:
1. A context-fit assessment for each proposed job
2. One or more bounded jobs (split if needed)
3. Allocator alias resolution for each job

This is the bridge between "Human approves objective" and "Job Queue".
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from context_fit_spike import (
    HandoffCharacteristics, evaluate_fit, create_continuation,
    is_executable, FIT_STATES,
)
from job_queue.models import JobRepository


@dataclass
class CompiledJob:
    """A job produced by the Handoff Compiler."""
    goal: str
    flow_key: str
    role_key: str
    target_project: str
    allocator_alias: str = ""
    context_fit_state: str = ""
    parent_goal: str = ""
    continuation_index: int = 0
    is_continuation: bool = False


def compile_handoff(
    goal: str,
    flow_key: str,
    role_key: str,
    target_project: str,
    model_context_window: int,
) -> list[CompiledJob]:
    """Compile an approved goal into bounded jobs.
    
    Steps:
    1. Estimate handoff characteristics from goal text
    2. Evaluate context fit
    3. If FITS or FITS_WITH_LOW_MARGIN → single job
    4. If SPLIT_REQUIRED → split into continuations
    5. If LARGER_MODEL_REQUIRED → single job with warning
    """
    # Estimate characteristics from goal
    goal_tokens = len(goal) // 4
    estimated_files = max(1, goal_tokens // 200)
    
    ch = HandoffCharacteristics(
        goal_text=goal,
        changed_file_count=estimated_files,
        architectural_spread=min(5, estimated_files),
        verification_scope=2,
        governance_files_count=2,
        requires_file_reads=estimated_files,
        estimated_lines_per_file=100,
    )
    
    fit_state, budget = evaluate_fit(ch, model_context_window)
    
    if is_executable(fit_state):
        # Single job
        return [CompiledJob(
            goal=goal,
            flow_key=flow_key,
            role_key=role_key,
            target_project=target_project,
            context_fit_state=fit_state,
        )]
    
    if fit_state == "SPLIT_REQUIRED":
        # Split into continuations
        plan = create_continuation(ch, model_context_window)
        if plan and plan.continuations:
            jobs = []
            for i, cont in enumerate(plan.continuations):
                cont_fit, _ = evaluate_fit(cont, model_context_window)
                jobs.append(CompiledJob(
                    goal=cont.goal_text,
                    flow_key=flow_key,
                    role_key=role_key,
                    target_project=target_project,
                    context_fit_state=cont_fit,
                    parent_goal=goal,
                    continuation_index=i,
                    is_continuation=True,
                ))
            return jobs
    
    # LARGER_MODEL_REQUIRED or CONTEXT_REDUCTION_REQUIRED → single job with warning
    return [CompiledJob(
        goal=goal,
        flow_key=flow_key,
        role_key=role_key,
        target_project=target_project,
        context_fit_state=fit_state,
    )]


def create_jobs_from_compiled(
    repo: JobRepository,
    compiled_jobs: list[CompiledJob],
    allocator_alias: str = "",
) -> list[str]:
    """Create Job Queue entries from compiled jobs. Returns job_ids."""
    job_ids = []
    parent_id = None
    
    for i, cj in enumerate(compiled_jobs):
        job_id = repo.create_job(
            flow_key=cj.flow_key,
            role_key=cj.role_key,
            goal=cj.goal,
            target_project=cj.target_project,
            allocator_alias=allocator_alias,
            parent_job_id=parent_id or "",
        )
        repo.update(job_id, context_fit_state=cj.context_fit_state)
        if i == 0 and cj.is_continuation:
            parent_id = job_id
        job_ids.append(job_id)
    
    return job_ids
