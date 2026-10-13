"""Detached semantic vision reports; possession grants no execution authority."""

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
from ..visual_evidence_observer import (
    VisualEvidenceMethod,
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)


SEMANTIC_VISION_SCHEMA_VERSION = 1

MAX_SEMANTIC_LABELS = 8
MAX_SEMANTIC_LABEL_LENGTH = 64


class SemanticVisionOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SemanticVisionFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    UPSTREAM_EVIDENCE_FAILED = "UPSTREAM_EVIDENCE_FAILED"
    ADAPTER_UNAVAILABLE = "ADAPTER_UNAVAILABLE"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class SemanticVisionMethod(str, Enum):
    STRUCTURED_VISION_V1 = "STRUCTURED_VISION_V1"


class SceneSetting(str, Enum):
    INDOOR = "INDOOR"
    OUTDOOR = "OUTDOOR"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ShotScale(str, Enum):
    EXTREME_WIDE = "EXTREME_WIDE"
    WIDE = "WIDE"
    MEDIUM = "MEDIUM"
    CLOSE_UP = "CLOSE_UP"
    EXTREME_CLOSE_UP = "EXTREME_CLOSE_UP"
    UNKNOWN = "UNKNOWN"


class VisualMood(str, Enum):
    CALM = "CALM"
    POSITIVE = "POSITIVE"
    ENERGETIC = "ENERGETIC"
    TENSE = "TENSE"
    SOMBER = "SOMBER"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SemanticLabel:
    label: str
    confidence_milli: int


@dataclass(frozen=True)
class SemanticVisionObservation:
    schema_version: int
    method: SemanticVisionMethod

    evidence: VisualEvidenceObservation

    scene_setting: SceneSetting
    shot_scale: ShotScale
    visual_mood: VisualMood

    subjects: tuple
    activities: tuple
    scene_tags: tuple

    confidence_milli: int


@dataclass(frozen=True)
class SemanticVisionResult:
    outcome: SemanticVisionOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    observation: SemanticVisionObservation | None
    failure_code: SemanticVisionFailureCode | None


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


def _validate_label_text(value):
    if (
        type(value) is not str
        or len(value) <= 0
        or len(value) > MAX_SEMANTIC_LABEL_LENGTH
        or value != value.strip()
        or value != value.lower()
    ):
        raise ValueError()

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789"
        " _-"
    )

    if any(
        character not in allowed
        for character in value
    ):
        raise ValueError()

    if "  " in value:
        raise ValueError()


def validate_semantic_label(label):
    try:
        _validate_exact_shape(
            label,
            SemanticLabel,
        )

        _validate_label_text(
            label.label
        )

        _validate_confidence(
            label.confidence_milli
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "semantic_label_invalid"
        ) from None

    return label


def _validate_label_collection(value):
    if type(value) is not tuple:
        raise ValueError()

    if len(value) > MAX_SEMANTIC_LABELS:
        raise ValueError()

    previous_key = None
    seen = set()

    for item in value:
        validate_semantic_label(
            item
        )

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


def validate_semantic_vision_observation(observation):
    """Validate one detached structured semantic vision observation."""
    try:
        _validate_exact_shape(
            observation,
            SemanticVisionObservation,
        )

        if (
            type(observation.schema_version) is not int
            or observation.schema_version
            != SEMANTIC_VISION_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(observation.method)
            is not SemanticVisionMethod
            or observation.method
            is not SemanticVisionMethod.STRUCTURED_VISION_V1
        ):
            raise ValueError()

        validate_visual_evidence_observation(
            observation.evidence
        )

        if (
            type(observation.evidence.method)
            is not VisualEvidenceMethod
            or observation.evidence.method
            is not VisualEvidenceMethod.DETERMINISTIC_RASTER_FEATURES_V1
        ):
            raise ValueError()

        if type(observation.scene_setting) is not SceneSetting:
            raise ValueError()

        if type(observation.shot_scale) is not ShotScale:
            raise ValueError()

        if type(observation.visual_mood) is not VisualMood:
            raise ValueError()

        _validate_label_collection(
            observation.subjects
        )

        _validate_label_collection(
            observation.activities
        )

        _validate_label_collection(
            observation.scene_tags
        )

        _validate_confidence(
            observation.confidence_milli
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "semantic_vision_observation_invalid"
        ) from None

    return observation


def validate_semantic_vision_result(result):
    """Validate detached result shape without granting execution authority."""
    try:
        _validate_exact_shape(
            result,
            SemanticVisionResult,
        )

        if type(result.outcome) is not SemanticVisionOutcome:
            raise ValueError()

        if result.outcome is SemanticVisionOutcome.SUCCESS:
            if result.failure_code is not None:
                raise ValueError()

            validate_descriptor(
                result.descriptor
            )

            validate_encoded_profile(
                result.profile
            )

            validate_semantic_vision_observation(
                result.observation
            )

            features = (
                result.observation
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

        elif result.outcome is SemanticVisionOutcome.FAILURE:
            if (
                result.descriptor is not None
                or result.profile is not None
                or result.observation is not None
                or type(result.failure_code)
                is not SemanticVisionFailureCode
                or not any(
                    result.failure_code is code
                    for code
                    in SemanticVisionFailureCode
                )
            ):
                raise ValueError()

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "semantic_vision_result_invalid"
        ) from None

    return result