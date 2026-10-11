# M65 — Visual Director Foundation

M65 is deliberately assigned to **Visual Director Foundation** in the current
roadmap, superseding the historical Voice Studio/TTS assignment in AGENTS.md.
This milestone ends here; M66 is not implemented.

The boundary is text → M64 SemanticDocument/StoryUnits → M65 VisualPlan → future
retrieval. M64 remains the semantic source of truth. No narration is duplicated
in visual state. No providers, queries, assets, media inspection, generation,
voice, subtitles, timing, scenes, GUI, or rendering are implemented.

## Persistent domain

`manifest/visual.py` contains typed enums, planning options/specification,
requirements, evidence, mention references, continuity, constraints, reviews,
plans, and signature helpers. `manifest/visual_validation.py` validates this
domain without importing visual runtime or orchestration.

Manifest schema remains 2. The only added top-level field is `visual_planning`,
with historical `plans` and `active_creator_plan_id`. Missing state migrates to
an empty state; present null, partial, unknown-field, or malformed state fails
strict decoding. Loading never selects a historical plan or repairs a reference.

A plan binds one creator semantic document, its captured output signature,
content revision, ordered complete StoryUnit list, semantic input fingerprint,
and full effective PlanningSpec. Units may group noncontiguous ordered refs;
separate units and shots may share StoryUnits. Shots must reference a nonempty
ordered subset of their parent's refs. Every StoryUnit must be covered. Empty
plans and zero-shot units are rejected; NO_VISUAL is not supported in M65.

Mention references bind StoryUnit ID, zero-based mention ordinal, and the exact
serialized mention fingerprint, including position. There is no text matching,
similarity recovery, entity resolution, or implicit reference promotion.

Requirements use a bounded treatment enum (SHOW, ILLUSTRATE, SYMBOLIZE, EVOKE,
TEXTUAL), evidence, provenance, optional confidence, and optional subject identity
fidelity. These express creative instructions, never new semantic facts.
Geography/temporal fidelity assertions require corresponding semantic mention
evidence; project context cannot establish source-bound geography. No geography
proxies or relative-date resolution occur. Continuity records have explicit
members/evidence and provenance; there is no global inference. Constraints are
bounded, typed, evidence/provenance checked, and reject required contradictions,
including across unit and shot constraints. Preferences do not promise matching
assets. Confidence is finite float in [0, 1], excluding bool.

Historical validity and current eligibility are separate. A semantic review can
retain the document ID while changing its output signature. Existing visual
history stays valid/loadable but becomes ineligible. Eligibility additionally
requires the current creator semantic document and requested specifications.

## Runtime and atomicity

`models.py` exposes typed ID-free candidates. `planner.py` defines VisualPlanner
and OfflineStructuralPlanner. The engine passes isolated document/options copies.
The baseline returns one unit and one shot per StoryUnit, all interpretive fields
UNKNOWN, with no requirements, geography, temporal, continuity, or constraints.
PlanningOptions is intentionally empty: no fake configuration or unused options.

`engine.py` owns identities and persistence. It validates caller state, resolves
current semantic input, invokes the planner, constructs authoritative records,
and fully validates one copied manifest proposal. Exceptions become fixed safe
diagnostics; cancellation before publication discards the proposal. The caller,
semantic state, scenes, and active selection remain unchanged on failure.

Plan/unit/shot reviews use M64 ReviewStatus and strict bool locks. APPROVED or
locked at any level protects the active plan, even when stale. A different-ID
candidate fails with `visual_review_required`; no candidate is appended. Same-ID
execution preserves all existing review/lock metadata. Unlocked PENDING and
REJECTED records allow replacement. No force flag, field locks, or override merge.

## Identities

All signatures reuse M64 `exact_signature`, which serializes through the M61
codec with ASCII escapes before calling the existing M61 signature utility.
There is no parallel hashing implementation.

1. Semantic input fingerprint binds document ID, exact captured output signature,
   content revision, retained source revision ID, ordered StoryUnit IDs, purpose.
2. Planning signature binds that fingerprint, complete PlanningSpec (contract,
   engine, planner ID/version, typed options), and creator purpose.
3. Generated digest signs ordered ID-free units/shots and controlled diagnostics.
   It excludes reviews, generated IDs, derived parent IDs, and output signatures.
4. Plan ID signs planning signature and generated digest. Unit and shot IDs sign
   their parent ID, ordinal, refs, and generated payload, without circular hashes.
5. Output signature includes every persisted plan field except itself, including
   reviews, locks, provenance, diagnostics, and children.

Identity contains no clock, random value, attempt, source locator, asset, voice,
timing, or render state. Lookup maps and bounded traversals keep visual processing
approximately linear in explicit records/references and retained history; no
all-pairs comparison or complete-plan hashing inside child loops is used.

## M62 integration and H1/H2 protections

`stage.py` provides only `visual_director`, version `1`. Dependencies default to
`()`, and may be configured as `("semantic_story",)`. No orchestrator changes.
Stage inputs bind semantic input, exact retained source representation, complete
PlanningSpec, required semantic specification, and creator purpose. Current
visual output is deliberately excluded.

Artifacts are exactly these references and digests in this order:

1. `visual/<plan_id>` binds recomputed output signature, planning signature,
   semantic input fingerprint, and exact retained source binding.
2. `visual_semantic/<document_id>` binds semantic output/analysis/content
   signatures, ordered StoryUnit IDs, source revision ID, and source binding.
3. `semantic_source/<source_revision_id>` equals independently recomputed
   `exact_signature(retained_source.content)`.

This implements H1: formatting or locator changes to authoritative retained
source invalidate execution reuse even if semantic revision/visual identity is
unchanged. Artifacts expose no text or locator. The retained source, not a newer
equivalent canonical record, is authoritative for this binding.

M62 verifies current execution dependency/configuration signature before invoking
the domain reuse hook. The hook validates the whole manifest, exact retained
execution identity/version/status/signature, current creator semantic input and
required specs, eligible active visual output, exact three artifacts, and offline
baseline recomputation of generated content excluding reviews. Future planners
default to no reuse. Self-consistent generated-output/artifact forgery cannot
bypass the baseline comparison.

This implements H2: changed input/spec runs execution, which enforces review
protection. Reviewed output is never a shortcut to reuse. A visual review edit
invalidates old artifacts; same-ID execution preserves review and refreshes
artifacts, allowing subsequent reuse.

## Verification

Run `python -m unittest tests.test_visual_director -v`, the M61–M64 suites, and
offline Semantic Window, Context Geography, and Visual Strategy regressions.
Tests include contract/reference matrices, historical staleness, reviewed/locked
regeneration, source binding, forged output, cancellation, Unicode persistence,
legacy additive loading, import/field boundaries, and 2,000 StoryUnits.

Known foundation limits: no semantic interpretation or visual inference; no
NO_VISUAL disposition; no behavior-changing baseline options; no safe reuse
policy for non-baseline planners. Future retrieval must derive its own requests
from typed visual contracts and semantic references without changing M64 truth.
