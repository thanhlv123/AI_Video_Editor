"""Detached semantic vision adapter data contract.

Possession of an adapter request grants no source execution authority.
"""

from dataclasses import dataclass, fields

from ..bounded_raster_sampling import (
    BoundedRasterObservation,
    validate_bounded_raster_observation,
)
from ..visual_evidence_observer import (
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)
from .models import (
    MAX_SEMANTIC_LABELS,
    SceneSetting,
    SemanticLabel,
    ShotScale,
    VisualMood,
    validate_semantic_label,
)


SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SemanticVisionAdapterRequest:
    schema_version: int
    raster: BoundedRasterObservation
    evidence: VisualEvidenceObservation


@dataclass(frozen=True)
class SemanticVisionAdapterResponse:
    schema_version: int

    scene_setting: SceneSetting
    shot_scale: ShotScale
    visual_mood: VisualMood

    subjects: tuple
    activities: tuple
    scene_tags: tuple

    confidence_milli: int


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


def _validate_confidence(value):
    if (
        type(value) is not int
        or value < 0
        or value > 1000
    ):
        raise ValueError()


def _validate_label_collection(value):
    if type(value) is not tuple:
        raise ValueError()

    if len(value) > MAX_SEMANTIC_LABELS:
        raise ValueError()

    seen = set()
    previous_key = None

    for item in value:
        validate_semantic_label(
            item
        )

        if type(item) is not SemanticLabel:
            raise ValueError()

        if item.label in seen:
            raise ValueError()

        seen.add(
            item.label
        )

        key = (
            -item.confidence_milli,
            item.label,
        )

        if (
            previous_key is not None
            and key < previous_key
        ):
            raise ValueError()

        previous_key = key


def validate_semantic_vision_adapter_request(request):
    """Validate one detached request passed toward a future vision adapter."""
    try:
        _validate_exact_shape(
            request,
            SemanticVisionAdapterRequest,
        )

        if (
            type(request.schema_version) is not int
            or request.schema_version
            != SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ):
            raise ValueError()

        validate_bounded_raster_observation(
            request.raster
        )

        validate_visual_evidence_observation(
            request.evidence
        )

        if type(request.raster) is not BoundedRasterObservation:
            raise ValueError()

        if type(request.evidence) is not VisualEvidenceObservation:
            raise ValueError()

        features = request.evidence.features

        if (
            request.raster.source_width
            != features.source_width
        ):
            raise ValueError()

        if (
            request.raster.source_height
            != features.source_height
        ):
            raise ValueError()

        if (
            request.raster.width
            != features.width
        ):
            raise ValueError()

        if (
            request.raster.height
            != features.height
        ):
            raise ValueError()

        if (
            request.raster.width
            * request.raster.height
            != features.pixel_count
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "semantic_vision_adapter_request_invalid"
        ) from None

    return request


def validate_semantic_vision_adapter_response(response):
    """Validate one normalized response returned by a future vision adapter."""
    try:
        _validate_exact_shape(
            response,
            SemanticVisionAdapterResponse,
        )

        if (
            type(response.schema_version) is not int
            or response.schema_version
            != SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ):
            raise ValueError()

        if type(response.scene_setting) is not SceneSetting:
            raise ValueError()

        if type(response.shot_scale) is not ShotScale:
            raise ValueError()

        if type(response.visual_mood) is not VisualMood:
            raise ValueError()

        _validate_label_collection(
            response.subjects
        )

        _validate_label_collection(
            response.activities
        )

        _validate_label_collection(
            response.scene_tags
        )

        _validate_confidence(
            response.confidence_milli
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "semantic_vision_adapter_response_invalid"
        ) from None

    return response