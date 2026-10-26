"""Score and quality output reject contradictory claims."""

import pytest
from pydantic import ValidationError

from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12
from tkb_core.contracts.score import QualityReport, RuleScore, ScoreReport, StageRun


def test_scores_exact_and_error_not_partial() -> None:
    row = RuleScore(
        rule_id="r",
        code="x",
        priority=1,
        weight=3,
        unit="teaching_periods",
        raw_penalty=2,
        weighted_penalty=6,
    )
    score = ScoreReport(status="OK", input_fingerprint="a" * 64, rules=(row,), tiers=(6, 0, 0))
    assert score.tiers == (6, 0, 0)
    with pytest.raises(ValidationError):
        RuleScore.model_validate({**row.model_dump(), "weighted_penalty": 5})
    with pytest.raises(ValidationError):
        ScoreReport(status="OK", input_fingerprint="a" * 64, rules=(row,), tiers=(5, 0, 0))
    with pytest.raises(ValidationError):
        ScoreReport(status="INVALID_SCHEDULE", rules=(row,), tiers=(6, 0, 0))


def test_quality_guard_and_legacy_shape() -> None:
    with pytest.raises(ValidationError):
        QualityReport(status="LEXICOGRAPHIC_OPTIMAL", score=None, optimal_prefix=(), tier_runs=())
    result = ScheduleResult(
        schema_version="1.1", status="UNKNOWN", metadata={"solver_executed": False}
    )
    assert "quality" not in result.model_dump()
    with pytest.raises(ValidationError):
        ScheduleResult.model_validate({**result.model_dump(), "quality": None})


def test_output_v12_roundtrip_and_quality_guards() -> None:
    score = ScoreReport(status="OK", input_fingerprint="a" * 64, rules=(), tiers=(0, 0, 0))
    q = QualityReport(
        status="SCORED_FEASIBLE",
        score=score,
        optimal_prefix=(),
        tier_runs=(StageRun(priority=1, raw_status="NOT_RUN"),),
    )
    from tkb_core.contracts.output import ValidationReport

    r = ScheduleResult(
        schema_version="1.2",
        status="FEASIBLE",
        input_fingerprint="a" * 64,
        valid_schedule=True,
        validation=ValidationReport(valid=True),
        metadata=SolverRunMetadataV12(solver_executed=False),
        quality=q,
    )
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r
    with pytest.raises(ValidationError):
        ScheduleResult.model_validate({**r.model_dump(), "input_fingerprint": "b" * 64})
