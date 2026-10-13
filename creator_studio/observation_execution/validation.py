"""Bounded exact structural validation, with no authority upgrade."""
from .models import (
    ObservationExecutionSpec, ObservationExecutionState,
    ObserverExecutionDescription, ObservationExecutionRecord,
    ObservationExecutionAssessment, ObservationExecutionError,
)
from ..source_observation.models import (
    ObservationCoverage, AssessmentBoundary, SourceObservationError,
)
from ..source_observation.validation import (
    preflight as _upstream_preflight, validate_spec as _validate_observation_spec,
    validate_claim as _validate_claim,
)
from ..source_snapshot.models import SourceSnapshotError
from ..source_snapshot.validation import validate_descriptor as _validate_descriptor


def _require(condition):
    if not condition:
        raise ObservationExecutionError()


def _preflight(value, schema):
    # M76's schema-directed walker accepts these exact dataclasses as roots.
    # One invocation covers the ENTIRE graph before any semantic access/equality.
    # Its 32-depth / 2,000,000-node bounds charge repeated references per visit,
    # reject cycles/subclasses/extra fields, and retain all M76 fact capacities.
    try:
        _upstream_preflight(value, schema)
    except SourceObservationError:
        raise ObservationExecutionError() from None


def validate_observation_execution_spec(spec):
    _preflight(spec, ObservationExecutionSpec)
    _require(spec.contract_version == spec.engine_version == "1")
    return spec


def validate_observer_execution_description(observer):
    _preflight(observer, ObserverExecutionDescription)
    for label in (observer.observer_id, observer.observer_version,
                  observer.observation_method_id, observer.observation_method_version,
                  observer.fact_mapping_version):
        _require(len(label) > 0)
    return observer


def validate_observation_execution_record(record):
    _preflight(record, ObservationExecutionRecord)
    validate_observation_execution_spec(record.spec)
    validate_observer_execution_description(record.observer)
    try:
        _validate_descriptor(record.snapshot_descriptor)
        _validate_observation_spec(record.observation_spec)
        if record.claim is not None:
            _validate_claim(record.claim)
    except (SourceObservationError, SourceSnapshotError):
        raise ObservationExecutionError() from None
    if record.execution_state is ObservationExecutionState.SUCCEEDED:
        _require(record.claim is not None)
        _require(record.declared_observation_coverage in (
            ObservationCoverage.PARTIAL, ObservationCoverage.COMPLETE))
    else:
        _require(record.claim is None)
        _require(record.declared_observation_coverage is ObservationCoverage.ABSENT)
    if record.claim is not None:
        claim, observer = record.claim, record.observer
        # Exact upstream identity includes asset_id, sha256 AND byte_count.
        _require(claim.byte_identity == record.snapshot_descriptor.byte_identity)
        _require(claim.observer_id == observer.observer_id)
        _require(claim.observer_version == observer.observer_version)
        _require(claim.observation_method_id == observer.observation_method_id)
        _require(claim.observation_method_version == observer.observation_method_version)
        _require(all(stream.source_kind is observer.source_kind
                     for stream in claim.visual_streams))
    return record


def validate_observation_execution_assessment(assessment):
    _preflight(assessment, ObservationExecutionAssessment)
    _require(assessment.structurally_valid is True)
    _require(all(value is AssessmentBoundary.NOT_ASSESSED for value in (
        assessment.physical_byte_verification, assessment.physical_observation_authority,
        assessment.observation_execution, assessment.presentation_compliance,
        assessment.renderer_adapter_compatibility, assessment.executability)))
    return assessment
