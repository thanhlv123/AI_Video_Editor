# M72 render timeline foundation

M72 is a retained single visual lane scheduling projection, never a renderer or
an adapter into `manifest.timeline`. Schema remains 2. Missing state defaults to
empty history; present malformed state is rejected by strict decoding.

Each M69 placement retains its identity/order, exact M68 materialization and asset
evidence, and exact M71 timing evidence. Historical validation is pure and ignores
current pointers. Current eligibility delegates the existing M71 logical and
narration chain with explicitly supplied expected policies/specifications.
An incomplete active plan can be eligible and reused. Inactive history is never
searched for reuse or reactivated; identity collisions reject atomically.
Even builder reuse requires successful/skipped M62 execution evidence, exact
stage version, dependencies and ordered artifacts. Retained entries alone do not
authorize reuse. Supply `acquisition_spec`, `edit_spec`, and `timing_spec` when
expecting upstream configurations other than their contract defaults. M71 and
M70 acceptance policy/version arguments and narration storage remain explicit.

`DETERMINISTIC_STILL_OR_EXACT_WHOLE_VIDEO_V1` permits a still image for the full
M71 interval or a whole video whose retained duration exactly matches that interval.
`M68_RETAINED_BINARY_DURATION_EXACT_US_V1` uses `float.as_integer_ratio` and integer
division, with no rounding or tolerance. Exactness concerns the retained float,
not frames or stream timestamps. Unsupported kinds, missing media, unresolved
timing, nonintegral durations, and longer/shorter videos remain explanatory.
No caller trims, transformations, tracks, FPS, gap fillers or executable rendering
authority exist. Times are half-open integer microseconds; bool/float times fail.

Completeness requires nonempty exact placement coverage and READY source-use
decisions, independently of continuity, media bytes, legal review or executability.
`uncovered_intervals` observes leading/interior/trailing uncovered narration spans
without persisting gaps. `observe_media_usability` separately delegates M68 with
trusted injected storage/inspection collaborators and mutation fences.

Stage `render_timeline`, version `1`, accepts only `()` or
`("media_acquisition", "edit_planning", "placement_timing")`. Dependency iterables
are consumed once, requesting at most four elements. Exactly two ordered logical
artifacts bind the render plan and M71 timing plus captured media/edit evidence.

Limits: 64 plans, 4096 entries per plan, 65536 historical entries, 16 diagnostics
per entry, 64 MiB canonical plan, 4097 derived uncovered intervals. Capacity
preflight precedes recursive validation, hashing/copying and observations.
Canonical accounting traverses bounded records incrementally; it does not protect
raw JSON document parsing. Cancellation is cooperative at explicit boundaries,
not inside hashing, serialization, copying or arbitrary blocking collaborators.
Builders return a validated copy changing only M72. Hashes establish integrity,
not authenticated approval. No providers, media tools or rendering are invoked.
