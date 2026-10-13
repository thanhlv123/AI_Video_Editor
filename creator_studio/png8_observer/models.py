"""Detached structural reports; possession grants no execution authority."""
from dataclasses import dataclass, fields
from enum import Enum
from ..source_snapshot import SourceSnapshotDescriptor, validate_descriptor
from ..still_image_observation_method import EncodedStillImageProfile, validate_encoded_profile


class PNG8PreflightOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class PNG8PreflightFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    STRUCTURAL_INVALID = "STRUCTURAL_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


@dataclass(frozen=True)
class PNG8PreflightResult:
    outcome: PNG8PreflightOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    failure_code: PNG8PreflightFailureCode | None


def validate_preflight_result(result):
    """Validate detached shape only, using one sanitized validation error."""
    try:
        if type(result) is not PNG8PreflightResult:
            raise ValueError()
        members = object.__getattribute__(result, "__dict__")
        names = {f.name for f in fields(PNG8PreflightResult)}
        if (type(members) is not dict or len(members) != len(names)
                or any(type(k) is not str for k in members) or set(members) != names):
            raise ValueError()
        if type(result.outcome) is not PNG8PreflightOutcome:
            raise ValueError()
        if result.outcome is PNG8PreflightOutcome.SUCCESS:
            if result.failure_code is not None:
                raise ValueError()
            validate_descriptor(result.descriptor)
            validate_encoded_profile(result.profile)
        elif (result.outcome is not PNG8PreflightOutcome.FAILURE
              or result.descriptor is not None or result.profile is not None
              or type(result.failure_code) is not PNG8PreflightFailureCode
              or not any(result.failure_code is code for code in PNG8PreflightFailureCode)):
            raise ValueError()
    except MemoryError:
        raise
    except Exception:
        raise ValueError("png8_preflight_result_invalid") from None
    return result
