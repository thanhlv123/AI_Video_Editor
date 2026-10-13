"""Pure validation of detached declarations; success authenticates nothing."""
from dataclasses import fields
from .models import (
    StillImageObservationMethodSpec, EncodedStillImageProfile,
    StillImageObservationMethodError, MAX_INPUT_BYTES, MAX_CODED_AXIS,
    MAX_DECODED_PIXELS, ENCODED_MODES,
)
from ..observation_execution.validation import validate_observer_execution_description
from ..observation_execution.models import ObservationExecutionError
from ..source_observation.models import (
    SourceObservationError, SourceKind, ExactRational, Orientation,
    OtherDisplayTransformStatus, AlphaPresence, EffectiveOpacity,
    PresentationMultiplicity, TimestampEnumerationStatus, TimestampOrigin,
    FrameObservation,
)
from ..source_observation.validation import validate_claim, validate_byte_identity


def _require(condition):
    if not condition:
        raise StillImageObservationMethodError()


def _record(value, schema):
    # Small fixed records need no recursive graph walker.
    _require(type(value) is schema)
    members = object.__getattribute__(value, "__dict__")
    names = tuple(field.name for field in fields(schema))
    _require(type(members) is dict and len(members) == len(names))
    _require(all(type(key) is str for key in members))
    _require(set(members) == set(names))
    return members


def validate_method_spec(spec):
    members = _record(spec, StillImageObservationMethodSpec)
    version = members["contract_version"]
    _require(type(version) is str)
    _require(len(version) == 1 and version == "1")
    try:
        validate_observer_execution_description(members["observer"])
    except ObservationExecutionError:
        raise StillImageObservationMethodError() from None
    expected = StillImageObservationMethodSpec().observer
    _require(spec.observer == expected)
    return spec


def validate_encoded_profile(profile):
    members = _record(profile, EncodedStillImageProfile)
    _require(all(type(value) is int for value in members.values()))
    w, h = profile.coded_width_px, profile.coded_height_px
    _require(0 < w <= MAX_CODED_AXIS and 0 < h <= MAX_CODED_AXIS)
    _require(w * h <= MAX_DECODED_PIXELS)
    _require(any((profile.bit_depth, profile.color_type) == row[:2]
                 for row in ENCODED_MODES))
    _require(profile.compression_method == profile.filter_method == profile.interlace_method == 0)
    _require(0 < profile.phys_x_pixels_per_unit <= 4294967295)
    _require(profile.phys_x_pixels_per_unit == profile.phys_y_pixels_per_unit)
    _require(profile.phys_unit_specifier == 0)
    return profile


def validate_fact_mapping(profile, claim, byte_identity):
    """Check declared M76 facts against V1, not actual media or M77 authority.

    byte_identity is the detached expected identity. Only a future runtime can
    establish that it is M77-verified and that these declarations are true.
    """
    validate_encoded_profile(profile)
    try:
        validate_byte_identity(byte_identity)
        validate_claim(claim)
    except SourceObservationError:
        raise StillImageObservationMethodError() from None
    _require(byte_identity.byte_count <= MAX_INPUT_BYTES)
    _require(claim.byte_identity == byte_identity)
    observer = StillImageObservationMethodSpec().observer
    _require(all(getattr(claim, name) == getattr(observer, name) for name in (
        "observer_id", "observer_version", "observation_method_id", "observation_method_version")))
    _require(claim.visual_stream_inventory_complete is True)
    _require(len(claim.visual_streams) == 1 and claim.container_duration_us is None)
    stream = claim.visual_streams[0]
    w, h = profile.coded_width_px, profile.coded_height_px
    mode = next(row[2] for row in ENCODED_MODES if row[:2] == (profile.bit_depth, profile.color_type))
    _require(stream.stream_index == 0 and stream.source_kind is SourceKind.STILL_IMAGE)
    _require(stream.coded_width_px == w and stream.coded_height_px == h)
    _require(stream.display_width == ExactRational(w, 1))
    _require(stream.display_height == ExactRational(h, 1))
    _require(stream.sample_aspect_ratio == ExactRational(1, 1))
    _require(stream.reported_display_aspect_ratio is None)
    _require(stream.orientation is Orientation.IDENTITY)
    _require(stream.rotation_degrees == ExactRational(0, 1))
    _require(stream.other_display_transform_status is OtherDisplayTransformStatus.ABSENT)
    _require(stream.pixel_format == mode)
    has_alpha = mode in ("LA", "RGBA")
    _require(stream.alpha_presence is (AlphaPresence.PRESENT if has_alpha else AlphaPresence.ABSENT))
    _require(stream.effective_opacity in (EffectiveOpacity.OPAQUE, EffectiveOpacity.NOT_OPAQUE))
    _require(has_alpha or stream.effective_opacity is EffectiveOpacity.OPAQUE)
    _require(stream.decoded_presentation_count == 1)
    _require(stream.presentation_multiplicity is PresentationMultiplicity.SINGLE_STILL)
    _require(all(getattr(stream, name) is None for name in (
        "nominal_frame_rate", "average_frame_rate", "time_base", "stream_start_ticks",
        "stream_duration_ticks", "presentation_start_ticks", "presentation_end_exclusive_ticks")))
    _require(stream.timestamp_enumeration_status is TimestampEnumerationStatus.COMPLETE)
    _require(stream.frames == (FrameObservation(0, None, None, TimestampOrigin.UNKNOWN),))
    return claim
