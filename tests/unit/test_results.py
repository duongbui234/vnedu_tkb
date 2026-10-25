"""Version-specific metadata shapes, not fake execution evidence."""

import pytest
from pydantic import ValidationError

from tkb_core.contracts.output import ScheduleResult


def test_v1_roundtrip_does_not_add_new_metadata_fields() -> None:
    old = {"schema_version": "1.0", "status": "NOT_RUN"}
    result = ScheduleResult.model_validate(old)
    assert set(result.model_dump()["metadata"]) == {
        "solver_version",
        "wall_time",
        "objective_value",
        "best_bound",
    }


def test_new_metadata_is_not_mislabeled_as_old_schema() -> None:
    with pytest.raises(ValidationError):
        ScheduleResult.model_validate(
            {"schema_version": "1.0", "status": "NOT_RUN", "metadata": {"solver_executed": False}}
        )


def test_v11_metadata_records_no_execution_explicitly() -> None:
    result = ScheduleResult.model_validate(
        {"schema_version": "1.1", "status": "UNKNOWN", "metadata": {"solver_executed": False}}
    )
    assert not result.metadata.solver_executed
