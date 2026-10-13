"""M82 detached bounded raster sampling API."""

from .models import (
    MAX_SAMPLE_AXIS,
    MAX_SAMPLE_PIXELS,
    BoundedRasterFailureCode,
    BoundedRasterObservation,
    BoundedRasterOutcome,
    BoundedRasterPixelFormat,
    BoundedRasterResult,
    BoundedRasterSamplingMethod,
    validate_bounded_raster_observation,
    validate_bounded_raster_result,
)
from .runtime import BoundedRasterSamplingRuntime


__all__ = (
    "MAX_SAMPLE_AXIS",
    "MAX_SAMPLE_PIXELS",
    "BoundedRasterFailureCode",
    "BoundedRasterObservation",
    "BoundedRasterOutcome",
    "BoundedRasterPixelFormat",
    "BoundedRasterResult",
    "BoundedRasterSamplingMethod",
    "validate_bounded_raster_observation",
    "validate_bounded_raster_result",
    "BoundedRasterSamplingRuntime",
)