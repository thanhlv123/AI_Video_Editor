# Placement Timing Foundation (M71)

M71 projects immutable M69 placement IDs onto narration-relative integer
microseconds. It changes only `ProjectManifest.placement_timing`. M69 retains
`TimingState.UNRESOLVED`; this domain creates no render timeline.

`PlacementTimingStage` uses stage ID `placement_timing`, version `1`. Dependencies
are exactly `()` or `("edit_planning", "voice_timing")`, normalized once on entry.
Registration is explicit; M62 owns execution metadata.

Call `build_placement_timing` with narration storage, expected M70 alignment spec
and acceptance policy, M71 spec/policy, and optional declarations. There is no
default acceptance gate. The injected `PlacementTimingAcceptanceGate` makes a
project policy decision; it does not authenticate a person or verify acoustics.
`make_receipt` is a construction utility, never an acceptance implementation.

Accepted source allocations bind exact placement/source/document/StoryUnit IDs,
half-open source coordinates and exact excerpt signatures. Explicit declarations
bind one placement side to an integer microsecond. Declarations have deterministic
references and are retained in input order. Competing sources for the same side
are rejected. One plan-level receipt covers the complete proposal, including
unresolved entries.

`M70_LEXICAL_ENVELOPE_V1` uses retained M70 unit endpoints without interpolation.
Non-whitespace source coverage must be complete. Omissions, mismatches, unmapped
speech, added speech and unrelated intervening units block derivation. A partial
edge requires explicit editorial authority for that side. Positive gaps between
supporting units may be inside an envelope; they are not verified silence.
Explicit accepted intervals may cut units or cover leading/trailing/gap/added
speech regions. Derived timing never expands to audio zero or narration duration.

Without declarations, the builder may create a gate-free all-unresolved
observation. It has no request signature, receipt, intervals or boundary evidence.
With any declaration, the gate is mandatory even if all entries stay unresolved.

Historical validation uses retained source/semantic chain evidence, including
captured semantic output, independently of current review and active pointers.
It performs no filesystem, storage, network, provider or gate access. Current
eligibility separately requires exact active logical M69/M70 bindings, expected
specs/policies and M70 narration-byte verification. It never calls M68 media
usability or M69 current edit eligibility. A nonmaterialized placement can be
TIMED. Completeness is derived from eligible, nonempty, fully TIMED placement
coverage with receipt/evidence; gaps and partial whole-audio coverage are allowed.

Reuse is active-only and requires exact declarations, bindings, receipt, stage
and dependency execution evidence, and two ordered artifacts:

1. `placement_timing/<placement_timing_plan_id>`
2. `placement_timing_edit/<edit_plan_id>`

No history candidate is promoted or repaired. Exact reuse does not call the gate
or upgrade an incomplete observation. Callback fences capture the complete
manifest, upstream logical bindings, configuration, declaration order, dependency
execution evidence and transient gate/storage identities. Final proposal checks
prevent partial updates; callbacks must not mutate their inputs.

Fixed v1 history limits live in `manifest/placement_timing.py`. Shallow capacity
checks precede public recursive validation and runtime serialization/copying.
Acceptance payloads use an explicit primitive JSON projection and incremental
ASCII byte accounting with a 64 MiB ceiling. Runtime requests contain only frozen
scalars and a tuple of placement IDs; no mutable manifest aliases are retained.
Cancellation is checked between operations and inside placement/allocation/unit
loops, never claimed inside generic serialization.

Identity is domain-separated: declarations → input → output → request → receipt
→ plan. Output excludes receipt/plan ID. A closed no-receipt discriminator identifies
observation plans. Hashes provide integrity bindings, not authentication.

No source paths, provider locators, credentials, raw transcript, callback identity,
media trims, FPS or render offsets are persisted. No media storage or inspector
is added. This foundation does not perform editing, alignment, rendering, speech
generation or provider calls.
