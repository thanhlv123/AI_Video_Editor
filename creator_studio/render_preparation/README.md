# RenderPreparation V1 (M73)

M73 retains explicit output geometry and a rational frame lattice, preparation
policies, exact upstream evidence, deterministic requirements, signatures and
bounded append-only history. It executes no rendering and defines no encoding
or export profile. OutputProfile has no dimension or FPS defaults. Policies are
explicit constructor arguments; no alternative policy is inferred.

M72 integer microseconds remain timing authority. Exact divisibility establishes
frame alignment without rounding or frame indices. Output duration is the exact
M70 narration duration reached through M72 and M71. Supported resolved M72
intervals determine coverage of [0, narration duration); gaps remain requirements.
No filler, transformations, retiming, audio mixing or subtitle output is created.
Visual source audio is explicitly muted, regardless of unknown audio presence.
Narration preserves M70 inspection evidence and PCM frame zero.

Dimension equality establishes only dimension comparison. Image SAR, rotation
and alpha are unestablished. Whole-video cadence, PTS/timebase, SAR and rotation
are unestablished. These produce closed outstanding requirements, so matching
dimensions and aligned times cannot promise successful export.

`current_logically_eligible` validates retained current lineage and expected
configuration without storage access. Historical reconstruction resolves exact
retained identities independently of active upstream pointers and invokes no
collaborators. `assess_render_preparation` separately observes upstream combined
eligibility, narration usability, and aggregate relevant-media usability. The
aggregate observation cannot attribute current byte failures to placements.
Transient observations and collaborator identity never persist or affect hashes.
Renderer compatibility and executability remain NOT_ASSESSED.

The builder returns a copy differing only in render_preparation. Failures publish
no partial M73 state; arbitrary external malicious side effects cannot be rolled
back. Observation fences preflight before callbacks and immediately after them,
then recheck callable/configuration and manifest integrity. Hashes establish
integrity, not authenticated approval.

History is limited to 64 plans and 65536 aggregate entry assessments. Reuse is
active-only, requires exact M62 execution evidence, stage version/configuration,
dependencies and two ordered logical artifacts. Matching inactive history is a
collision, never reactivated. Blocked results may be retained and reused exactly;
current byte usability is always a separate observation.

The stage is render_preparation version 1, with dependencies () or
("render_timeline",). Artifacts are render_preparation/<M73 plan ID> and
render_preparation_timeline/<M72 plan ID>. There are no physical output artifacts.
The contract defines no container, codec, pixel format, conversion, bitrate, CRF,
preset, muxer, faststart, output location, renderer or executable capability.
