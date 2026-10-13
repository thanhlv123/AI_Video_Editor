# M76 byte-bound source observation contract

M76 represents explicitly supplied source observation **CLAIMS**. It does not
collect observations, verify bytes, authenticate an observer, establish physical
truth, establish presentation compliance, clear M73 blockers, establish renderer
compatibility, or establish executability. It is transient, offline, and pure.

Claims bind to declared `asset_id`, `sha256`, and `byte_count`, reusing M68's
`asset:sha256:` identity relationship. Live logical binding checks these against
retained M68 records, after M75 live authority runs upstream first through its
public live API. M75 rejects a supplied draft differing from the fresh current
draft. M76 full-proposal equality is retained as a defensive invariant but is
redundant under current deterministic V1 for detached-valid divergence.
It is not a normally reachable stale-proposal rejection gate.
M75 V1 offers no alternate valid policy tuple for stale-policy equality testing. No bytes or storage are accessed.
Physical byte verification remains `NOT_ASSESSED`. A future milestone must
perform trusted physical observation over verified controlled bytes, and another
authority must assess presentation compliance. M75 intent and its embedded M74
draft remain intact, including both M73 presentation blockers.

All records are frozen exact dataclasses; nested collections are tuples. Specs
require explicit V1 strings. Optional facts use None; ambiguous states use closed
enums. Unknown facts are never inferred from rates, counts, dimensions, or format.
Rationals preserve the supplied numerator and positive denominator without
reduction; equality is representation equality, not mathematical equivalence.
All integers have signed 63-bit-compatible magnitude; counts are nonnegative.
Byte counts require exact built-in int (bool rejected) in 1..536870912,
mirroring M68 MaterializedAsset V1 semantics; MAX_INTEGER is not their ceiling.
Dimensions have axis and area bounds, including rational display dimensions.

Frame durations may be zero. Presentation-order ordinals must strictly increase;
PARTIAL requires one or more observations, may skip ordinals, and does not claim
complete enumeration. ABSENT means zero supplied frame observations.
COMPLETE is structurally complete according to count/ordinal rules: known decoded
count, equal frame count, and contiguous ordinals from zero. COMPLETE with zero
decoded frames and zero frame observations is structurally representable.
This establishes neither physical completeness nor policy compliance. PTS may be missing, negative, duplicate, or nonmonotonic.
No sorting, repair, timestamp synthesis, or lattice checking occurs. A reported
exclusive end cannot precede a reported start. SINGLE_STILL contradicts a known
count other than one; MULTI_FRAME/ANIMATED contradict a known count below two.
Explicit simple orientation and rotation reports must agree when both supplied.
Inventory completeness is only a claim; indices are unique even for partial
inventories. visual_stream_inventory_complete=True with visual_streams=()
means the supplied claim reports zero visual streams, not authenticated physical
truth. No stream is selected for rendering.

Bindings retain exact M75 obligation order, identities, and evidence signatures.
ABSENT has a None index; PRESENT has an in-range claim index. Shared claims are
allowed. Unreferenced claims are retained without live authority; live checks
apply to referenced claims. Coverage COMPLETE means every obligation has a claim,
not that facts are known or trusted. An empty obligation set has ABSENT coverage.
Detached assessment always reports current_logically_bound=False; current
assessment rebuilds live authority each time. The bundle itself stores no grant.

V1 limits: 4096 bindings/claims, 16 streams per claim, 65536 frames per claim,
131072 frames per bundle, traversal depth 32 and 2000000 node occurrences,
strings 256, upstream IDs 96, axes 16384, area 100000000. Oversize evidence rejects
without truncation. Shared references consume occurrence budget; ancestry detects
cycles. Exact storage and keys are established before lookup. Errors are fixed
and never echo supplied labels. There is no M76 serialization or digest; the
reserved 64 MiB canonical limit does not cause serialization to be introduced.
Upstream M75/M74 bounds and structural validation continue to apply independently.

All five assessment boundaries remain NOT_ASSESSED:
physical_byte_verification, physical_observation_authority,
presentation_compliance, renderer_adapter_compatibility, executability.
