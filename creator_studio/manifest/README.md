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

# M66 additive retrieval extension

`ProjectManifest.retrieval` stores bounded discovery history and an optional active
retrieval ID. Candidates are not canonical `MediaReference` objects. No retrieval
operation changes `media`, `scenes`, or upstream reviewed truth. Rights is now
defined once in `rights.py` and re-exported from `models.py`; values and JSON
encoding are unchanged.

Schema version remains 2. Migration inserts an empty retrieval state only when
the field is absent. Present null, partial, malformed or unknown-field payloads
fail strict decoding/validation. Historical structure/signatures are validated
separately from current eligibility; review and upstream changes do not silently
reactivate runs or remove history. See `creator_studio/retrieval/README.md` for
limits, signatures, provider policy and the two exact stage artifacts.

# M68 additive acquisition extension

`ProjectManifest.acquisition` retains bounded AcquisitionRuns, MaterializationRecords
and digest-addressed MaterializedAssets with an explicit active pointer. Schema
remains 2; only absent acquisition fields receive an empty state. Present malformed
state fails strict decoding. Historical validation is pure, filesystem-free and
does not require current upstream activation or local object existence. Captured
effective selection review signatures bind an actual retained review prefix.
Runtime current usability and execution reuse are separate checks. No canonical
MediaReference or final approval is created. See acquisition/README.md for storage,
trust, cancellation, object-first publication and current runtime constraints.

# M67 additive logical selection extension

`ProjectManifest.selection` adds bounded immutable logical SelectionRun history,
append-only exact-choice SelectionReview transitions and an explicit active ID.
Schema remains 2. Missing selection receives an empty state during migration;
present malformed data fails strict decoding. Migration never fabricates history.
SelectedCandidateRef stores only candidate_id and metadata_fingerprint. All
descriptor and provenance observations remain authoritative in retained M66 runs.
Selection never authorizes rights or creates canonical MediaReference objects.
Historical validity is independent of active pointers; current eligibility and
effective reviewed output are explicit pure projections. See selection/README.md
for hard-evidence policy, protected replacement, bounds and stage contracts.


## M69 editing extension (schema 2)

`editing: EditingState` stores bounded deterministic EditPlans with ordered
EditPlacements, closed EditSpec, retained acquisition/upstream signatures, and only
`TimingState.UNRESOLVED`. Missing editing in older schema-2 documents defaults to
empty history and no active pointer; malformed present editing fails strict decoding.
Historical validation reconstructs retained lineage without filesystem access or
current-eligibility calls. Current usability and reuse belong to the isolated
`creator_studio.editing` runtime. Canonical media and timeline remain independent.
See `../editing/README.md` for eligibility, artifact, callback, and deferred boundaries.

## M70 voice timing extension (schema 2)

`voice_timing: VoiceTimingState` adds bounded narration byte identities, logical
revisions, strict PCM_WAV_V1 inspection, semantic source spans, accepted lexical
microsecond timing and receipts, with explicit active narration/alignment pointers.
Missing state defaults to empty; malformed present state and unknown fields fail.
Migration fabricates no audio, timing or acceptance. Historical validation is
filesystem-free; current audio usability rehashes bytes separately. Legacy Voice,
scenes, subtitles, media, timeline and M69 EditPlans confer no M70 authority.
See `../voice_timing/README.md` for trust boundaries and current eligibility.

# M71 placement timing

Schema remains **2**. `placement_timing` defaults to an empty
`PlacementTimingState`. Migration supplies this complete empty field only when
absent; present null, partial, malformed or unknown-field contracts fail strict
decoding. No timing authority is fabricated.

The separate retained domain contains specs, compact source/semantic lineage,
ordered exact source allocations and explicit microsecond boundaries, per-side
evidence, ordered entries and one optional plan-level acceptance receipt.
Persisted collections use lists; runtime policy requests use frozen scalar
projections. Completeness and current eligibility are observations, not mutable
manifest truth. See [M71 contracts](../placement_timing/README.md).

# M73 additive RenderPreparation

Schema remains 2. Missing render_preparation loads as empty history with no active
plan. Present records require every field and reject unknown fields. Raw capacity
preflight precedes migration copying; typed preflight precedes recursive validation.
Migration creates no output profile, policies, timing or preparation authority.
See [RenderPreparation V1](../render_preparation/README.md) for retained versus
transient boundaries. Historical preparation is reconstructed from exact retained
M72/M71/M70 evidence, independently of current upstream pointers and bytes.
