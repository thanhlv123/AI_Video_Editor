"""M79 detached still-image method contract. No runtime or authority."""
from .models import (
    StillImageObservationMethodSpec, EncodedStillImageProfile,
    StillImageObservationMethodError, MAX_INPUT_BYTES, MAX_CODED_AXIS,
    MAX_DECODED_PIXELS, ACCEPTED_PRESENTATIONS, FORMAT, PNG_SIGNATURE_HEX,
    CHUNK_GRAMMAR, ALLOWED_CHUNKS, ENCODED_MODES,
    STRUCTURAL_OBLIGATIONS, COMPLETE_OBLIGATIONS,
)
from .validation import validate_method_spec, validate_encoded_profile, validate_fact_mapping

__all__ = (
    "StillImageObservationMethodSpec", "EncodedStillImageProfile",
    "StillImageObservationMethodError", "MAX_INPUT_BYTES", "MAX_CODED_AXIS",
    "MAX_DECODED_PIXELS", "ACCEPTED_PRESENTATIONS", "FORMAT", "PNG_SIGNATURE_HEX",
    "CHUNK_GRAMMAR", "ALLOWED_CHUNKS", "ENCODED_MODES",
    "STRUCTURAL_OBLIGATIONS", "COMPLETE_OBLIGATIONS",
    "validate_method_spec", "validate_encoded_profile", "validate_fact_mapping",
)
