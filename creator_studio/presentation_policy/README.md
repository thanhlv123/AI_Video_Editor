# M75 Presentation Policy Contract

M75 defines PRESENTATION INTENT, not SOURCE PRESENTATION COMPLIANCE.
It is transient and reproducible, with no Manifest integration or persistence.
Callers explicitly supply every PresentationPolicySpec field: versions "1" and
"1", then the six PresentationChoice members in declaration order. There is
one closed V1 family; missing, unknown, or alternate choices reject.

Still images require a single still held for the exact half-open integer
microsecond interval, exact output display geometry, square pixels, zero
rotation, and opaque presentation. No scaling, cropping, padding, reframing,
SAR conversion, transformation, or runtime inference is authorized.

Whole videos require the same display facts plus exact output rational frame
lattice compliance and M72 WHOLE_VIDEO source coordinates. No retiming, trim,
loop, freeze, speed change, reverse, frame duplication, frame dropping, or FPS
conversion is authorized. Rational rates are retained verbatim, including
30000/1001. No physical compliance is inferred from dimensions, format,
duration, names, or retained inspection evidence.

One ordered obligation binds each supported clip's source identity, interval,
materialization_evidence_signature, asset_evidence_signature, and exact retained
source_width_px and source_height_px from its corresponding M74 assessment.
Optional dimensions preserve None exactly; target dimensions remain separate.
These fields reproduce retained logical evidence only. They do not authenticate
provenance, establish source presentation compliance, or discharge M73
presentation blockers. Physical display properties require a future
source-evidence milestone.
Unresolved or unsupported source use rejects the entire proposal; it is never
repaired or omitted. Gaps and other upstream blockers are not hidden.

M75 does not remove IMAGE_PRESENTATION_NOT_ESTABLISHED or
SOURCE_PRESENTATION_NOT_ESTABLISHED. The exact M74 draft is retained, including
all requirements. Matching dimensions do not discharge these obligations.
A future source-evidence milestone must verify physical display/frame facts,
including orientation, SAR, rotation, opacity, timestamps and cadence.

Detached validation proves bounded structural consistency and deterministic
reconstruction only. Integrity is not authentication or original provenance.
Live construction delegates authority to M74 build_render_job_draft and requires
exact supplied/fresh equality. Live assessment alone can report current logical
binding, and only for that call's snapshot. Invalid inputs raise ValueError;
no partial proposal or invalid assessment is published.

Source compliance, renderer adapter compatibility, and executability always
remain NOT_ASSESSED. M75 does not create RenderJobSpec. Normal visual jobs
remain logically incomplete. Legacy renderer defaults carry no authority.
There are no runtime collaborators, paths, encoding choices, or media reads.

Records are frozen and nested collections are tuples. Exact-schema preflight
precedes validation/equality/publication, rejects unknown fields and hostile
objects without their hooks, and allows repeated acyclic references. Limits:
4096 obligations, depth 32, 2,000,000 traversal occurrences, signed 63-bit
nonnegative integers, 256-character scalars (upstream IDs additionally follow
M74's 96-character rule). No canonical payload API or digest is introduced;
the 64 MiB constant is reserved and M74 enforces its projected payload limit.
