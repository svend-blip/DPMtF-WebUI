"""The learning-governance documents bind closure drafting and admission."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
GOV = DOCS / "governance-templates-v2"
ARTIFACT = DOCS / "LEARNING-ARTIFACT.md"
DECOMPOSER = GOV / "EXECUTION_DECOMPOSER.md"
SUPERVISOR = GOV / "SUPERVISOR_PLANNING.md"

FIFTEEN_KEYS = {
    "topic",
    "scope",
    "repository",
    "family",
    "run",
    "problem",
    "approach",
    "result",
    "failed_approaches",
    "important_files",
    "architecture_implications",
    "validation",
    "confidence",
    "supersedes",
    "admitted_by",
}
VALIDATION_KEYS = {"evidence_level", "verdicts", "testgoals"}
LEVELS = (
    "tests",
    "measured_runtime",
    "approved_architecture",
    "reviewer_conclusion",
    "observation",
)


def _read(path):
    return path.read_text(encoding="utf-8")


def test_learning_artifact_doc_lists_the_schema():
    text = _read(ARTIFACT)
    for key in FIFTEEN_KEYS:
        assert key in text, key
    for key in VALIDATION_KEYS:
        assert key in text, key
    ordered = re.search(
        r"`tests`,\s*`measured_runtime`,\s*`approved_architecture`,"
        r"\s*`reviewer_conclusion`,\s*`observation`",
        text,
    )
    assert ordered is not None, "the five levels must appear in strength order"
    assert "hypothesis" in text
    assert "never admitted" in text
    assert "admitted_by: pending" in text


def test_learning_artifact_example_has_exactly_the_required_keys():
    pytest.importorskip("yaml")
    import yaml

    text = _read(ARTIFACT)
    match = re.search(r"```yaml\n(.*?)\n```", text, re.S)
    assert match, "no yaml fence found in docs/LEARNING-ARTIFACT.md"
    data = yaml.safe_load(match.group(1))
    assert set(data) == FIFTEEN_KEYS, sorted(set(data) ^ FIFTEEN_KEYS)
    assert data["scope"] == "experience"
    assert set(data["validation"]) == VALIDATION_KEYS
    assert data["validation"]["evidence_level"] in LEVELS


def test_decomposer_governance_binds_the_learning_draft():
    text = _read(DECOMPOSER)
    assert "## Learning Draft at Closure" in text
    assert "LEARNING-DRAFT.yaml" in text
    assert "> Learning: none" in text
    assert "docs/LEARNING-ARTIFACT.md" in text
    assert "never calls the service" in text


def test_supervisor_governance_binds_admission():
    text = _read(SUPERVISOR)
    assert "learning admit" in text
    assert "admitted_by" in text
    assert "learning <admitted|rejected|edited|retracted|superseded>" in text
    phase3 = text.split("### Phase 3 — Draft", 1)[1].split("### Phase 4", 1)[0]
    phase6 = text.split("### Phase 6 — Close the Run and loop", 1)[1]
    phase6 = phase6.split("\n## ", 1)[0]
    assert "Learning:" in phase3
    assert "Learning:" in phase6


def test_learning_governance_names_no_absolute_paths():
    for path in (ARTIFACT, DECOMPOSER, SUPERVISOR):
        assert "/home/" not in _read(path), path
