"""Exact-type structural checks only; no I/O or live authority."""
from ..source_observation import validate_byte_identity, SourceObservationError
from .models import (
    SourceSnapshotError, SourceSnapshotSpec, SourceSnapshotRequest,
    SourceSnapshotDescriptor, SourceSnapshotResult, SourceSnapshotOutcome,
    SourceSnapshotFailureCode, IMPLEMENTATION_ID, METHOD_ID,
    MAX_DESCRIPTOR_STRING_LENGTH,
)

def _require(condition):
    if not condition:
        raise SourceSnapshotError()

def _record(value, cls, names):
    _require(type(value) is cls)
    members = object.__getattribute__(value, "__dict__")
    _require(type(members) is dict and len(members) == len(names))
    _require(all(type(k) is str for k in members))
    _require(set(members) == set(names))

def _identity(value):
    try:
        validate_byte_identity(value)
    except SourceObservationError:
        raise SourceSnapshotError() from None

def validate_spec(spec):
    names = ("contract_version", "engine_version", "max_snapshot_bytes",
             "read_chunk_bytes", "max_concurrent_captures",
             "max_outstanding_snapshots", "deadline_seconds",
             "extra_eof_check_bytes", "max_descriptor_string_length")
    _record(spec, SourceSnapshotSpec, names)
    for name, expected in zip(names, ("1", "1", 33554432, 1048576, 1, 1, 30, 1, 256)):
        value = object.__getattribute__(spec, name)
        _require(type(value) is type(expected))
        _require(value == expected)
    return spec

def validate_request(request):
    _record(request, SourceSnapshotRequest, ("byte_identity",))
    _identity(request.byte_identity)
    return request

def validate_descriptor(descriptor):
    names = ("byte_identity", "snapshot_implementation_id",
             "snapshot_implementation_version", "capture_method_id", "capture_method_version")
    _record(descriptor, SourceSnapshotDescriptor, names)
    _identity(descriptor.byte_identity)
    for name, expected in zip(names[1:], (IMPLEMENTATION_ID, "1", METHOD_ID, "1")):
        value = object.__getattribute__(descriptor, name)
        _require(type(value) is str)
        _require(len(value) <= MAX_DESCRIPTOR_STRING_LENGTH and value == expected)
    return descriptor

def validate_result(result):
    _record(result, SourceSnapshotResult, ("outcome", "descriptor", "failure_code"))
    _require(type(result.outcome) is SourceSnapshotOutcome)
    if result.outcome is SourceSnapshotOutcome.SUCCESS:
        _require(result.failure_code is None)
        validate_descriptor(result.descriptor)
    else:
        _require(result.outcome is SourceSnapshotOutcome.FAILURE)
        _require(result.descriptor is None)
        _require(type(result.failure_code) is SourceSnapshotFailureCode)
        _require(any(result.failure_code is member for member in SourceSnapshotFailureCode))
    return result
