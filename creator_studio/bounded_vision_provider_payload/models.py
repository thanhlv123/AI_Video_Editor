"""Detached bounded vision provider payload models.

Possession of a payload grants no source execution authority.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..bounded_raster_sampling import (
    MAX_SAMPLE_AXIS,
    MAX_SAMPLE_PIXELS,
)
from ..visual_evidence_observer import (
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)


VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION = 1

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

MAX_VISION_PROVIDER_IMAGE_BYTES = 6 * 1024 * 1024


class VisionProviderPayloadEncoding(str, Enum):
    PNG_RGBA8 = "PNG_RGBA8"


@dataclass(frozen=True)
class BoundedVisionProviderPayload:
    schema_version: int
    encoding: VisionProviderPayloadEncoding

    width: int
    height: int

    byte_length: int
    image_bytes: bytes

    evidence: VisualEvidenceObservation


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


def validate_bounded_vision_provider_payload(payload):
    """
    Validate one detached payload intended for a future vision provider.

    Validation confirms bounded structure only. It does not grant execution
    authority and does not perform network access.
    """
    try:
        _validate_exact_shape(
            payload,
            BoundedVisionProviderPayload,
        )

        if (
            type(payload.schema_version) is not int
            or payload.schema_version
            != VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(payload.encoding)
            is not VisionProviderPayloadEncoding
            or payload.encoding
            is not VisionProviderPayloadEncoding.PNG_RGBA8
        ):
            raise ValueError()

        if (
            type(payload.width) is not int
            or payload.width <= 0
            or payload.width > MAX_SAMPLE_AXIS
        ):
            raise ValueError()

        if (
            type(payload.height) is not int
            or payload.height <= 0
            or payload.height > MAX_SAMPLE_AXIS
        ):
            raise ValueError()

        if (
            payload.width
            * payload.height
            > MAX_SAMPLE_PIXELS
        ):
            raise ValueError()

        if type(payload.byte_length) is not int:
            raise ValueError()

        if (
            payload.byte_length <= 0
            or payload.byte_length
            > MAX_VISION_PROVIDER_IMAGE_BYTES
        ):
            raise ValueError()

        if type(payload.image_bytes) is not bytes:
            raise ValueError()

        if (
            len(payload.image_bytes)
            != payload.byte_length
        ):
            raise ValueError()

        if (
            len(payload.image_bytes)
            < len(PNG_SIGNATURE)
            or payload.image_bytes[
                :len(PNG_SIGNATURE)
            ]
            != PNG_SIGNATURE
        ):
            raise ValueError()

        validate_visual_evidence_observation(
            payload.evidence
        )

        if (
            type(payload.evidence)
            is not VisualEvidenceObservation
        ):
            raise ValueError()

        features = payload.evidence.features

        if (
            features.width
            != payload.width
        ):
            raise ValueError()

        if (
            features.height
            != payload.height
        ):
            raise ValueError()

        if (
            features.pixel_count
            != payload.width
            * payload.height
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "bounded_vision_provider_payload_invalid"
        ) from None

    return payload