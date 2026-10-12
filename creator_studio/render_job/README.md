# RenderJob Foundation (M74 V1)

Transient, renderer-neutral, logical, draft-first and fail-closed. This package
adds no Manifest field, migration, processing state, stage, dependency tuple,
artifact, history, cache, active pointer or M74 digest. Manifest schema remains 2.

`build_render_job_draft` requires an explicit output profile, preparation spec
and all nine expected upstream configuration keys accepted by M73. Every live
projection preflights the manifest, validates it, reconstructs the exact active
M73 authority and checks pure current logical eligibility. No runtime observation
or injected collaborators are used. Only allowlisted logical evidence is copied.

Drafts retain exact M73 requirements, ordered assessments, uncovered intervals,
bindings, narration evidence and M72 entry evidence. Nested collections are tuples.
Lane reasons are separate and deterministic. Timing uses half-open exact integer
microseconds; rational FPS stays rational. No interval repair or coverage trimming
occurs. Only retained still-image and whole-video source use is supported.

`validate_draft` accepts a detached structural projection. It guarantees exact
schema and type, boundedness, M72 row semantic coherence, the exact M72 V1
`RenderTimelineSpec()`, internal M72 signature consistency, deterministic M73
preparation consistency and exact M74 lane consistency. Its signatures and hashes
are deterministic integrity values, not authentication: a caller can mutate
detached data and recompute them. Detached validation does not prove original
asset provenance, original placement or order provenance, current active
authority, current logical eligibility, logical job constructibility, runtime
material usability, renderer compatibility or executability.

Only a live Manifest path can establish current authority. `assess_render_job_draft`
always leaves current eligibility and logical constructibility false, while
reporting preparation satisfaction separately. `construct_render_job_spec`
requires the live Manifest, supplied draft, explicit output profile, preparation
spec and complete expected upstream configuration. It freshly rebuilds the live
draft, requires exact equality with the supplied draft, then checks complete
logical conditions through `validate_spec_job`. A detached-only call cannot
construct a spec. `validate_spec_job` is a detached structural-completeness check;
it does not establish provenance or current authority. Normal supported entries
retain M73 image/source presentation blockers, so V1 cannot produce complete jobs
for them. Adapter compatibility and executability are always NOT_ASSESSED.

Identity geometry, bound narration, muted visual source audio and no subtitle
output policies are retained exactly. Audio inspection metadata is evidence only.
There is no encoding profile, renderer integration, legacy translation, path,
storage, filesystem access, byte verification, media inspection or subprocess.
Presentation compatibility, export encoding and runtime resolution/execution
belong to future milestones.
