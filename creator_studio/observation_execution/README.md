# M78 — Detached Observation Execution Contract

M78 is pure, deterministic structural validation, offline and transient. Its frozen
records DESCRIBE a proposed execution; they do not prove it occurred. Manual
construction, copying and reconstruction are structurally allowed and grant no
authority. Matching labels are descriptive, not authentication credentials.

M76 SourceObservationClaim remains a fact representation, not trusted observation
evidence. M77 SourceSnapshotDescriptor remains detached metadata, not live snapshot
authority. M78 does not call M77 runtime or consume snapshot bytes. A descriptor
may describe the full M68/M76 byte identity domain (1..536870912 bytes); this says
nothing about eligibility for M77's 33554432-byte runtime support limit.

ExecutionState values are declared only. NOT_EXECUTED and FAILED require no claim
and ABSENT coverage. SUCCEEDED requires a claim and PARTIAL or COMPLETE coverage.
SUCCEEDED does not mean trusted success. ObservationCoverage in M78 describes
declared physical observation coverage; it must not be confused with M76 bundle
obligation coverage. COMPLETE does not mean trusted physical completeness.
Inventory flags, timestamp status, frame counts and contiguous ordinals do not
establish completeness. fact_mapping_version describes a mapping contract; M78
neither executes nor authenticates a mapper.

Every structurally valid record assesses True for structurally_valid and
NOT_ASSESSED for all six boundaries: physical byte verification, physical
observation authority, observation execution, presentation compliance, renderer
adapter compatibility and executability. Even manually constructed
SUCCEEDED/COMPLETE records have exactly these results.

Validation reuses exact M76/M77 records and their structural validators. One M76
schema-directed preflight covers the entire M78 graph before semantic comparisons,
with depth 32 and 2,000,000 traversal nodes, charging repeated acyclic references
per occurrence. Exact fields/types, cycle rejection and M76 string/integer/stream/
frame/dimension bounds remain enforced. All errors use one sanitized message.
The builder preserves caller facts without normalization or synthesis.

There is no decoder/probe, media I/O, hashing, callback, registry, live capability,
Manifest, persistence, canonical serialization, evidence digest, compliance,
M73 blocker discharge or renderer. Detached records remain structurally valid
independently of any M77 capability lifetime, including after release; they never
carry authority. Natural Python copying or serialization conveys no authority.

A future trusted observer runtime may consume bytes while an M77 capability is
live, execute fixed trusted observer code, produce frozen M76 claim facts and issue
separate runtime-owned observation authority. That future authority may survive
M77 release by binding verified byte identity and completed execution. M78 does
none of this. Structural validation is deterministic for the same exact record;
physical observation determinism across dependency builds/platforms is not claimed.
