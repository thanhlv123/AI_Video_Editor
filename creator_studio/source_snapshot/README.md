# M77 — Bounded Verified Source Snapshot

M77 crosses runtime I/O. Success means this runtime owns an exact immutable
built-in bytes snapshot matching the requested M68 SHA-256 and byte count.
This establishes physical byte verification only for that live snapshot.

SourceSnapshotSpec explicitly requires all nine fixed V1 fields, with no defaults:
contract_version, engine_version, max_snapshot_bytes, read_chunk_bytes,
max_concurrent_captures, max_outstanding_snapshots, deadline_seconds,
extra_eof_check_bytes, and max_descriptor_string_length. Their values are
fixed and validated with exact built-in types (integers exclude bool).
Explicit V1 specification: versions "1"/"1", 33554432-byte capacity,
1048576-byte read chunks, one concurrent capture, one outstanding snapshot,
and a cooperative 30 second monotonic deadline. The extra EOF check requests
exactly one byte (extra_eof_check_bytes=1); the descriptor string maximum is
256 characters (max_descriptor_string_length=256). These are explicit spec
policy values, not caller-selectable bounds. M68 identities remain valid through 536870912 bytes (512 MiB);
assets above 32 MiB return SNAPSHOT_CAPACITY_EXCEEDED before resolution/open.

Requests contain only the existing M76 SourceByteIdentity. The canonical key
comes from public M68 object_key; public ManagedStorage.resolve is read-only.
There is one capture open, no storage verification followed by reopen. Short
reads loop within the declared count. Accumulation freezes once, then SHA-256
hashes the frozen bytes. Access returns that same payload without source I/O.
Release revokes access and frees the service slot. Detached records never mint
authority. Ordinary capability construction and serialization are rejected.

Use SourceSnapshotRuntime with an explicit absolute local managed-root string,
capture(spec, request, control=None), snapshot_bytes(capability), and
release(capability). Control may only be the existing exact public
orchestrator CancellationToken, with its built-in Event; no callbacks.
Invalid configuration/records raise sanitized SourceSnapshotError. Expected
runtime failures return closed failure codes, with no path or exception text.

M68/M77 assume trusted local managed storage root and ancestors. UNC/device
and network-style roots are rejected. Mapped remote drives cannot be proven
local by spelling and are unsupported, as is network storage. Hostile
filesystem mutation, reparse/symlink/check-open races, and malicious in-process
Python are outside V1's threat model. Trusted Python application code is the
boundary; this is not protection against introspection or plugins.

Same-path replacement may happen before/during open. Actual captured bytes
must still match identity. A changing source may succeed if its captured
sequence matches; no instantaneous filesystem-state or inode origin is proven.
After capture, modification/deletion of the original has no effect on the live
snapshot. M77 proves neither path immutability nor path freshness after capture.
No Windows locking guarantee is claimed. Deadline checks surround reads,
hash chunks and publication, but cannot interrupt an already blocked OS read.
Peak buffering may include accumulator, immutable payload and a read chunk;
there is no exact RSS guarantee.

M77 does not change M76 or its historical NOT_ASSESSED physical verification.
It does not clear M73 IMAGE_PRESENTATION_NOT_ESTABLISHED or
SOURCE_PRESENTATION_NOT_ESTABLISHED blockers. It does not probe or decode,
produce observation/presentation facts, authenticate an observer, assess
presentation compliance, renderer compatibility or executability, encode,
render, call providers, or integrate with Manifest. It does not persist bytes,
snapshots, authority, files, history or database state. Detached validation is
structural only. There is no canonical serialization or snapshot evidence
digest. Path-only future tools require a separately reviewed bridge.

V1 deterministic failure order: if physical source length differs from declared
byte_count, BYTE_COUNT_MISMATCH takes precedence. SHA256_MISMATCH is used
only after exact byte count has been established and the captured same-length
bytes produce the wrong digest.

Publication is failure-atomic: descriptor, success result, inactive capability,
and final return tuple are prepared before registration. A short state lock
registers the capability/lease and activates it; normal return uses the prepared
tuple without further ordinary allocation. A defensive Exception guard revokes
exactly this capability and clears its payload and current registration if the
publication/return boundary fails. No filesystem I/O, freeze or hash holds this
lock. Expected MemoryError maps to RESOURCE_EXHAUSTED after rollback; if
allocating that failure record also fails, MemoryError propagates without retry
or recursion, with no registered authority remaining. Recovery from every
possible allocator failure is not guaranteed. BaseException is not caught.
Copy, deepcopy and serialization of a live capability are rejected without
revoking the original. The outstanding-slot gate precedes resolution/open.
