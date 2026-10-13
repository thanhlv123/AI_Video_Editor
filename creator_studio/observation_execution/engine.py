"""Pure construction and assessment of detached descriptions."""
from .models import ObservationExecutionRecord, ObservationExecutionAssessment
from .validation import (
    validate_observation_execution_record, validate_observation_execution_assessment,
)
from ..source_observation.models import AssessmentBoundary


def build_observation_execution_record(*, spec, snapshot_descriptor,
                                       observation_spec, observer, execution_state,
                                       declared_observation_coverage, claim):
    return validate_observation_execution_record(ObservationExecutionRecord(
        spec, snapshot_descriptor, observation_spec, observer, execution_state,
        declared_observation_coverage, claim))


def assess_observation_execution(record):
    validate_observation_execution_record(record)
    boundary = AssessmentBoundary.NOT_ASSESSED
    return validate_observation_execution_assessment(ObservationExecutionAssessment(
        True, boundary, boundary, boundary, boundary, boundary, boundary))
