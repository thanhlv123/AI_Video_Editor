"""Private deterministic semantic vision observation builder.

Possession of detached evidence or adapter responses grants no execution
authority.
"""

from ..visual_evidence_observer import (
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)
from .adapter_contract import (
    SemanticVisionAdapterResponse,
    validate_semantic_vision_adapter_response,
)
from .models import (
    SEMANTIC_VISION_SCHEMA_VERSION,
    SemanticVisionFailureCode as Failure,
    SemanticVisionMethod,
    SemanticVisionObservation,
    validate_semantic_vision_observation,
)


class _SemanticBuildFailure(Exception):
    def __init__(self, code):
        self.code = code


def _build_semantic_observation(
    evidence,
    response,
    check,
):
    """
    Build one normalized M85 semantic observation.

    This function performs deterministic normalization only. It does not
    establish source authority and does not invoke any external provider.
    """
    try:
        validate_visual_evidence_observation(
            evidence
        )

    except MemoryError:
        raise _SemanticBuildFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _SemanticBuildFailure(
            Failure.UPSTREAM_EVIDENCE_FAILED
        ) from None

    if type(evidence) is not VisualEvidenceObservation:
        raise _SemanticBuildFailure(
            Failure.UPSTREAM_EVIDENCE_FAILED
        )

    try:
        validate_semantic_vision_adapter_response(
            response
        )

    except MemoryError:
        raise _SemanticBuildFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _SemanticBuildFailure(
            Failure.RESPONSE_INVALID
        ) from None

    if type(response) is not SemanticVisionAdapterResponse:
        raise _SemanticBuildFailure(
            Failure.RESPONSE_INVALID
        )

    try:
        check()

        observation = SemanticVisionObservation(
            schema_version=(
                SEMANTIC_VISION_SCHEMA_VERSION
            ),
            method=(
                SemanticVisionMethod
                .STRUCTURED_VISION_V1
            ),
            evidence=evidence,
            scene_setting=(
                response.scene_setting
            ),
            shot_scale=(
                response.shot_scale
            ),
            visual_mood=(
                response.visual_mood
            ),
            subjects=(
                response.subjects
            ),
            activities=(
                response.activities
            ),
            scene_tags=(
                response.scene_tags
            ),
            confidence_milli=(
                response.confidence_milli
            ),
        )

        try:
            validate_semantic_vision_observation(
                observation
            )

        except MemoryError:
            raise

        except Exception:
            raise _SemanticBuildFailure(
                Failure.RESPONSE_INVALID
            ) from None

        check()

        return observation

    except _SemanticBuildFailure:
        raise

    except MemoryError:
        raise _SemanticBuildFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None