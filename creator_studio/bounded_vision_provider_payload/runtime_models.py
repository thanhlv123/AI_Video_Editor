"""Detached M86 runtime result models.

Possession of a result or payload grants no source execution authority.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..source_snapshot import (
    SourceSnapshotDescriptor,
    validate_descriptor,
)
from ..still_image_observation_method import (
    EncodedStillImageProfile,
    validate_encoded_profile,
)
from .models import (
    BoundedVisionProviderPayload,
    validate_bounded_vision_provider_payload,
)


class BoundedVisionProviderPayloadOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class BoundedVisionProviderPayloadFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    UPSTREAM_RASTER_FAILED = "UPSTREAM_RASTER_FAILED"
    UPSTREAM_EVIDENCE_FAILED = "UPSTREAM_EVIDENCE_FAILED"
    COHERENCE_INVALID = "COHERENCE_INVALID"
    PAYLOAD_INVALID = "PAYLOAD_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


@dataclass(frozen=True)
class BoundedVisionProviderPayloadResult:
    outcome: BoundedVisionProviderPayloadOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    payload: BoundedVisionProviderPayload | None
    failure_code: BoundedVisionProviderPayloadFailureCode | None


def _validate_exact_shape(value, expected_type):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(expected_type)
    }

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(
            type(key) is not str
            for key in members
        )
        or set(members) != names
    ):
        raise ValueError()


def validate_bounded_vision_provider_payload_result(result):
    """
    Validate one detached M86 runtime result.

    Successful possession of this report does not grant execution authority.
    """
    try:
        _validate_exact_shape(
            result,
            BoundedVisionProviderPayloadResult,
        )

        if (
            type(result.outcome)
            is not BoundedVisionProviderPayloadOutcome
        ):
            raise ValueError()

        if (
            result.outcome
            is BoundedVisionProviderPayloadOutcome.SUCCESS
        ):
            if result.failure_code is not None:
                raise ValueError()

            validate_descriptor(
                result.descriptor
            )

            validate_encoded_profile(
                result.profile
            )

            validate_bounded_vision_provider_payload(
                result.payload
            )

            if (
                type(result.payload)
                is not BoundedVisionProviderPayload
            ):
                raise ValueError()

            features = (
                result.payload
                .evidence
                .features
            )

            if (
                features.source_width
                != result.profile.coded_width_px
            ):
                raise ValueError()

            if (
                features.source_height
                != result.profile.coded_height_px
            ):
                raise ValueError()

        elif (
            result.outcome
            is BoundedVisionProviderPayloadOutcome.FAILURE
        ):
            if (
                result.descriptor is not None
                or result.profile is not None
                or result.payload is not None
                or type(result.failure_code)
                is not BoundedVisionProviderPayloadFailureCode
                or not any(
                    result.failure_code is code
                    for code
                    in BoundedVisionProviderPayloadFailureCode
                )
            ):
                raise ValueError()

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "bounded_vision_provider_payload_result_invalid"
        ) from None

    return result