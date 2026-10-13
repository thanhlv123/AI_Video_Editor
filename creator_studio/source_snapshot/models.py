"""Detached V1 snapshot records. These records grant no live authority."""
from dataclasses import dataclass
from enum import Enum
from ..source_observation import SourceByteIdentity

MAX_SNAPSHOT_BYTES = 33554432
READ_CHUNK_BYTES = 1048576
MAX_CONCURRENT_CAPTURES = 1
MAX_OUTSTANDING_SNAPSHOTS = 1
DEADLINE_SECONDS = 30
EXTRA_EOF_CHECK_BYTES = 1
MAX_DESCRIPTOR_STRING_LENGTH = 256
IMPLEMENTATION_ID = "creator_studio.source_snapshot.runtime"
METHOD_ID = "creator_studio.source_snapshot.bounded_capture"

class SourceSnapshotError(ValueError):
    def __init__(self):
        super().__init__("source_snapshot_invalid")

class SourceSnapshotOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

class SourceSnapshotFailureCode(str, Enum):
    SOURCE_MISSING = "SOURCE_MISSING"
    SOURCE_ACCESS_FAILED = "SOURCE_ACCESS_FAILED"
    SOURCE_PATH_REJECTED = "SOURCE_PATH_REJECTED"
    SNAPSHOT_CAPACITY_EXCEEDED = "SNAPSHOT_CAPACITY_EXCEEDED"
    BYTE_COUNT_MISMATCH = "BYTE_COUNT_MISMATCH"
    SHA256_MISMATCH = "SHA256_MISMATCH"
    CANCELLED = "CANCELLED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"

@dataclass(frozen=True)
class SourceSnapshotSpec:
    contract_version: str
    engine_version: str
    max_snapshot_bytes: int
    read_chunk_bytes: int
    max_concurrent_captures: int
    max_outstanding_snapshots: int
    deadline_seconds: int
    extra_eof_check_bytes: int
    max_descriptor_string_length: int

@dataclass(frozen=True)
class SourceSnapshotRequest:
    byte_identity: SourceByteIdentity

@dataclass(frozen=True)
class SourceSnapshotDescriptor:
    byte_identity: SourceByteIdentity
    snapshot_implementation_id: str
    snapshot_implementation_version: str
    capture_method_id: str
    capture_method_version: str

@dataclass(frozen=True)
class SourceSnapshotResult:
    outcome: SourceSnapshotOutcome
    descriptor: SourceSnapshotDescriptor | None
    failure_code: SourceSnapshotFailureCode | None
