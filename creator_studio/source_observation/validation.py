"""Exact bounded graph preflight precedes semantic access and equality."""
from dataclasses import is_dataclass
from enum import Enum
from types import UnionType
from typing import get_args, get_origin, get_type_hints
import re
from .models import *
from ..presentation_policy import validate_proposal

# Compatibility ceiling mirrors M68 MaterializedAsset V1 semantics.
MAX_SOURCE_BYTE_COUNT = 536870912

def require(condition):
    if not condition:
        raise SourceObservationError()

def preflight(value, schema=SourceObservationBundle):
    remaining = MAX_TRAVERSAL_NODES
    ancestry = set()
    frame_total = 0
    def walk(item, expected, depth):
        nonlocal remaining, frame_total
        remaining -= 1
        require(remaining >= 0 and depth <= MAX_TRAVERSAL_DEPTH)
        origin = get_origin(expected)
        if origin is UnionType:
            selected = next((t for t in get_args(expected) if type(item) is t), None)
            require(selected is not None)
            walk(item, selected, depth)
            return
        if origin is tuple:
            require(type(item) is tuple)
            child_type = get_args(expected)[0]
            limit = {SourceObservationClaim: MAX_OBSERVATION_CLAIMS,
                     ObservationBinding: MAX_OBSERVATION_BINDINGS,
                     VisualStreamObservation: MAX_VISUAL_STREAMS_PER_CLAIM,
                     FrameObservation: MAX_FRAME_OBSERVATIONS_PER_CLAIM}.get(child_type, 4097)
            require(len(item) <= limit)
            if child_type is FrameObservation:
                frame_total += len(item)
                require(frame_total <= MAX_FRAME_OBSERVATIONS_PER_BUNDLE)
            container = True
        else:
            require(type(item) is expected)
            container = is_dataclass(expected)
        if container:
            require(id(item) not in ancestry)
            ancestry.add(id(item))
            try:
                if origin is tuple:
                    for child in item:
                        walk(child, child_type, depth + 1)
                else:
                    hints = get_type_hints(expected)
                    members = object.__getattribute__(item, "__dict__")
                    require(type(members) is dict and len(members) == len(hints))
                    for key in members:
                        require(type(key) is str)
                    require(set(members) == set(hints))
                    for key, child_schema in hints.items():
                        walk(members[key], child_schema, depth + 1)
            finally:
                ancestry.remove(id(item))
        elif expected is int:
            require(-MAX_INTEGER <= item <= MAX_INTEGER)
        elif expected is str:
            require(len(item) <= MAX_STRING_LENGTH)
        elif isinstance(expected, type) and issubclass(expected, Enum):
            require(any(item is member for member in expected))
        else:
            require(expected is bool or expected is type(None))
    walk(value, schema, 0)

def validate_spec(spec):
    preflight(spec, SourceObservationSpec)
    require(spec.contract_version == spec.engine_version == "1")
    return spec

def validate_byte_identity(identity):
    preflight(identity, SourceByteIdentity)
    require(re.fullmatch(r"[0-9a-f]{64}", identity.sha256) is not None)
    require(identity.asset_id == "asset:sha256:" + identity.sha256)
    require(type(identity.byte_count) is int and 0 < identity.byte_count <= MAX_SOURCE_BYTE_COUNT)
    return identity

def validate_rational(value):
    preflight(value, ExactRational)
    require(value.denominator > 0)
    return value

def _stream(stream):
    require(stream.stream_index >= 0)
    w, h = stream.coded_width_px, stream.coded_height_px
    for dimension in (w, h):
        require(dimension is None or 0 < dimension <= MAX_DIMENSION_AXIS)
    if w is not None and h is not None:
        require(w <= MAX_DIMENSION_AREA // h)
    for name in ("display_width", "display_height", "sample_aspect_ratio",
                 "reported_display_aspect_ratio", "nominal_frame_rate",
                 "average_frame_rate", "time_base", "rotation_degrees"):
        value = getattr(stream, name)
        if value is not None:
            require(value.denominator > 0)
            if name != "rotation_degrees":
                require(value.numerator > 0)
            if name in ("display_width", "display_height"):
                require(value.numerator <= MAX_DIMENSION_AXIS * value.denominator)
    if stream.display_width is not None and stream.display_height is not None:
        a, b = stream.display_width, stream.display_height
        require(a.numerator * b.numerator <= MAX_DIMENSION_AREA * a.denominator * b.denominator)
    for count in (stream.decoded_presentation_count, stream.stream_duration_ticks):
        require(count is None or count >= 0)
    if stream.presentation_start_ticks is not None and stream.presentation_end_exclusive_ticks is not None:
        require(stream.presentation_end_exclusive_ticks >= stream.presentation_start_ticks)
    previous = -1
    for frame in stream.frames:
        require(frame.ordinal > previous)
        previous = frame.ordinal
        require(frame.duration_ticks is None or frame.duration_ticks >= 0)
        if stream.decoded_presentation_count is not None:
            require(frame.ordinal < stream.decoded_presentation_count)
    status = stream.timestamp_enumeration_status
    if status is TimestampEnumerationStatus.ABSENT:
        require(not stream.frames)
    elif status is TimestampEnumerationStatus.PARTIAL:
        require(len(stream.frames) >= 1)
    elif status is TimestampEnumerationStatus.COMPLETE:
        require(stream.decoded_presentation_count is not None)
        require(len(stream.frames) == stream.decoded_presentation_count)
        require(all(f.ordinal == i for i, f in enumerate(stream.frames)))
    count = stream.decoded_presentation_count
    if stream.presentation_multiplicity is PresentationMultiplicity.SINGLE_STILL:
        require(count is None or count == 1)
    elif stream.presentation_multiplicity in (PresentationMultiplicity.MULTI_FRAME, PresentationMultiplicity.ANIMATED):
        require(count is None or count >= 2)
    if stream.orientation is Orientation.IDENTITY and stream.rotation_degrees is not None:
        require(stream.rotation_degrees.numerator == 0)
    for orientation, degrees in ((Orientation.ROTATED_90, 90), (Orientation.ROTATED_180, 180),
                                  (Orientation.ROTATED_270, 270)):
        if stream.orientation is orientation and stream.rotation_degrees is not None:
            require(stream.rotation_degrees.numerator == degrees * stream.rotation_degrees.denominator)

def validate_claim(claim):
    preflight(claim, SourceObservationClaim)
    validate_byte_identity(claim.byte_identity)
    for label in (claim.observer_id, claim.observer_version,
                  claim.observation_method_id, claim.observation_method_version):
        require(0 < len(label) <= MAX_STRING_LENGTH)
    require(claim.container_duration_us is None or claim.container_duration_us >= 0)
    require(len({s.stream_index for s in claim.visual_streams}) == len(claim.visual_streams))
    require(sum(len(s.frames) for s in claim.visual_streams) <= MAX_FRAME_OBSERVATIONS_PER_CLAIM)
    for stream in claim.visual_streams:
        _stream(stream)
    return claim

def validate_bundle(bundle):
    preflight(bundle)
    try:
        validate_proposal(bundle.proposal)
    except ValueError:
        raise SourceObservationError() from None
    validate_spec(bundle.spec)
    for claim in bundle.claims:
        validate_claim(claim)
    require(len(bundle.bindings) == len(bundle.proposal.obligations))
    names = ("ordinal", "placement_id", "materialization_id", "asset_id",
             "materialization_evidence_signature", "asset_evidence_signature")
    for i, (binding, obligation) in enumerate(zip(bundle.bindings, bundle.proposal.obligations)):
        require(binding.ordinal == i)
        require(all(getattr(binding, n) == getattr(obligation, n) for n in names))
        for name in ("placement_id", "materialization_id", "asset_id"):
            require(0 < len(getattr(binding, name)) <= MAX_UPSTREAM_ID_LENGTH)
        if binding.observation_status is ObservationReferenceStatus.ABSENT:
            require(binding.observation_index is None)
        else:
            index = binding.observation_index
            require(index is not None and 0 <= index < len(bundle.claims))
            require(bundle.claims[index].byte_identity.asset_id == binding.asset_id)
    return bundle

def coverage(bundle):
    count = sum(b.observation_status is ObservationReferenceStatus.PRESENT for b in bundle.bindings)
    return (ObservationCoverage.ABSENT if count == 0 else
            ObservationCoverage.COMPLETE if count == len(bundle.bindings) else ObservationCoverage.PARTIAL)
