# M69 timeline / editing foundation

This milestone is an ordered visual edit plan with unresolved timing. Text remains
semantic truth; voice will be timing truth when an authoritative timing contract
exists. This module has no renderable timeline or creator editing commands.

`build_edit_plan` accepts a manifest, expected `AcquisitionSpec`, closed `EditSpec`,
managed storage, trusted inspector, and cancellation control. It accepts no shot,
asset, materialization, local file, or timing overrides. It returns a copied manifest
whose only changed field is `editing`. Persisting the proposal belongs to M62.

## Retained truth and current observations

Historical validation is pure: exact M65 order is projected through retained M67
choices and M68 shot acquisitions, with equal lengths required before indexing.
Every planned shot has one placement, including NOT_SELECTED_UPSTREAM,
UNSUPPORTED_SOURCE, and RIGHTS_BLOCKED outcomes. Only MATERIALIZED carries a
materialization ID. Shared bytes or shared materializations never merge placements.
Materialization lineage retains the exact candidate fingerprint transitively.

The active plan is selected only by `active_creator_edit_plan_id`. Current eligibility
requires the exact active M64-M68 chain, effective M67 review state, expected
AcquisitionSpec, and independently reconstructed EditSpec/placement projection.
Historical plans survive upstream pointer changes, byte deletion, corruption,
inspector unavailability, and unrelated voice changes. These observations never
rewrite historical provenance.

M68 `current_usability` verifies all unique materializations in the exact active run
in one invocation. M69 deliberately retains that API's full digest, inspection,
and post-inspection digest checks. M68 owns per-asset cancellation and byte reading.
All-unresolved plans need no inspector. M69 captures authorization signatures before
verification and rechecks afterward, after proposal validation, and before successful
stage return. Callbacks changing required upstream authorization fail closed.

Coverage completeness is derived separately. Timing remains UNRESOLVED; final-use
readiness is NOT ESTABLISHED. No canonical media, eligibility flag, rights, timeline,
source range, duration, tracks, transforms, or executable transitions are produced.
Existing voice/scenes/subtitles/audio/timeline data do not authorize M69 timing.

## Identity, reuse, artifacts, bounds

Signatures bind acquisition identity/output, retained semantic/visual/retrieval/
selection signatures and captured effective review, closed EditSpec, and ordered
placements. IDs use deterministic exact signatures, without runtime objects,
storage locations, timestamps, random IDs, or availability observations.
The output signature excludes itself. Stable plan/placement IDs can be referenced
by future timing domains without changing M69 provenance.

Exactly two ordered artifacts bind `edit/<edit_plan_id>` and
`edit_acquisition/<acquisition_id>`. Their signatures cover plan/output/edit identity
and retained acquisition/materialization/asset/effective-selection evidence.
Artifacts persist references and digests only, with no locators or timing.

Reuse requires the explicit active plan, exact successful/skipped execution,
dependency signature, two exact ordered artifacts, reconstructed current projection,
and current M68 usability. There is no history-based reuse or inactive reactivation.
Collision detection may examine retained IDs, solely to reject inactive duplicates.
Direct builder reuse requires this same stage evidence. New plan capacity is checked
before byte verification; active reuse does not consume history capacity.
Limits: 64 plans, 4096 placements per plan, 65536 total historical placements.
No pruning, garbage collection, or repair occurs.

`EditPlanningStage` version 1 uses stage ID `edit_planning`; dependencies are either
empty or exactly `("media_acquisition",)`. Readiness is filesystem-free. Execution
reads managed bytes only through M68 and produces a validated proposal and two
artifacts. It never calls providers, staging, publication, network, or rendering.

## Limitations and deferred findings

Trusted inspectors are not sandboxed. They may mutate external state; M69 rejects
changed authorization but cannot undo arbitrary callback side effects. Current byte
verification and repeated logical validation can be expensive. The M62 reuse hook
has no cancellation argument; checks around that hook cannot interrupt its internal
work. Whole-manifest validation and signature serialization are not interruptible.
No authoritative voice timing, creator edit commands, rendering timeline, canonical
MediaReference promotion, or final legal approval exists in M69.

M68-L01, M67-L01/L02/L03, M66 M-01/L-01, and M65 conservative reuse are deferred
unchanged. M70+ is outside this implementation.
