"""Frozen detached descriptions. No record conveys observation authority."""
from dataclasses import dataclass
from enum import Enum
from ..source_observation.models import (
    SourceObservationSpec, SourceObservationClaim, SourceKind,
    ObservationCoverage, AssessmentBoundary,
)
from ..source_snapshot.models import SourceSnapshotDescriptor


class ObservationExecutionError(ValueError):
    def __init__(self):
        super().__init__("observation_execution_invalid")


@dataclass(frozen=True)
class ObservationExecutionSpec:
    contract_version: str
    engine_version: str


class ObservationExecutionState(str, Enum):
    NOT_EXECUTED = "NOT_EXECUTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ObserverExecutionDescription:
    observer_id: str
    observer_version: str
    observation_method_id: str
    observation_method_version: str
    fact_mapping_version: str
    source_kind: SourceKind


@dataclass(frozen=True)
class ObservationExecutionRecord:
    spec: ObservationExecutionSpec
    snapshot_descriptor: SourceSnapshotDescriptor
    observation_spec: SourceObservationSpec
    observer: ObserverExecutionDescription
    execution_state: ObservationExecutionState
    declared_observation_coverage: ObservationCoverage
    claim: SourceObservationClaim | None


@dataclass(frozen=True)
class ObservationExecutionAssessment:
    structurally_valid: bool
    physical_byte_verification: AssessmentBoundary
    physical_observation_authority: AssessmentBoundary
    observation_execution: AssessmentBoundary
    presentation_compliance: AssessmentBoundary
    renderer_adapter_compatibility: AssessmentBoundary
    executability: AssessmentBoundary
