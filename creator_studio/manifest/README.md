# Manifest V2 foundation

This package uses only the Python standard library. It does not integrate with
the legacy pipeline. Create `ProjectManifest(project_name="My project")`, then
use `validate`, `save`, and `load` through the package API.

IDs are opaque, case-sensitive, globally unique within a manifest. UUIDs are
allocated at construction only. Persisted documents require every contract field;
missing fields, unknown fields and duplicate JSON keys are rejected. Script spans
are half-open Python character offsets. Times are nonnegative seconds.

Unknown media defaults to REFERENCE_ONLY. Final selection requires explicit
eligibility plus OWNED, LICENSED or PUBLIC_DOMAIN rights. Virtual shots retain
source references and cannot bypass source eligibility. Review subtitle segments
reference original segments and share their timing, scene and original text.
Approval/lock fields are preserved; no regeneration operations are implemented.

Save validates before writing, closes and fsyncs a same-directory temporary file,
then atomically replaces the target. The previous validated revision is atomically
stored as `.bak`. Invalid existing targets are not overwritten. `recover_previous`
explicitly reads the backup without changing the target. Parent directories must
already exist. Callers must serialize concurrent saves; multi-process locking and
directory fsync/power-loss guarantees are outside this foundation.

Signatures use sorted JSON keys, NFC Unicode, ordered arrays and SHA-256. Integers
and floats remain distinct for untyped inputs and integer schema fields. Typed
float fields normalize to finite floats at construction, encoding and decoding
(including integer assignments made after construction). Validation checks the
original runtime typed graph without conversion or mutation. Stage signatures include a caller-supplied algorithm
revision and dependencies; callers choose relevant inputs to avoid invalidating
unrelated work. Nonfinite values and normalized key collisions are rejected.

Snapshot metadata is frozen and records a digest and recovery reference. The
caller must persist the referenced manifest separately before adding the metadata;
this milestone does not manage snapshot files or retention. A digest covers the
manifest at capture time, before appending its own snapshot metadata.

Migration occurs before decoding through `migrate_document`. Only schema 2 is
supported today; no legacy conversion is attempted. Future explicit sequential
migrations belong at this boundary. Diagnostics accept controlled codes and a
retry flag only; never pass credentials in any manifest text or provider fields.

Virtual-shot times use underlying physical-source coordinates. Each nested shot
must be contained within its parent; this applies at every ancestry level.
Scene-linked subtitles and timeline items must be contained within explicit scene
timing. Untimed scenes do not impose invented timing.

Media provenance rights are authoritative for final-media eligibility.
InputSource.rights is an ingest declaration and never upgrades media rights.
A permissive ingest declaration linked to REFERENCE_ONLY or UNKNOWN media is a
validation conflict, even when the media is not selected. Changing canonical
provenance requires a future explicit authorization workflow, not implemented here.

M64 adds `semantic: SemanticState` without changing schema version 2. Migration
supplies empty source_revisions/documents/selection only when semantic is absent;
present malformed data fails strict decoding. Persistent validation stays in
manifest/semantic_validation.py and never imports semantic runtime engines.

Retained SemanticSourceRevision records are historical evidence, deduplicated by
logical content ID and M63 revision signature. They preserve the exact originating
ContentRecord and an exact-record fingerprint; current content remains canonical.
SemanticDocuments retain revision-bound blocks, StoryUnits and exact code-point
source spans. Historical staleness is derived, not persisted as mutable state.
`eligible_active_document(manifest, required_spec)` returns None for stale output
without changing selection or history. REFERENCE_ANALYSIS cannot be selected as
creator output. Full semantic validation also checks historical document integrity.

Semantic IDs are deterministic type-prefixed signatures. Reviews are excluded
from generated analysis identity but included in exact output fingerprints.
Exact Unicode fingerprints ASCII-escape JSON before calling M61 signature().
Future Qt/JavaScript clients must convert UTF-16 positions to Python code points;
source spans never use bytes, graphemes or UTF-16 offsets. See semantic/README.md
for the offline baseline and stage contract.
