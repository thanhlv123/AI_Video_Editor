# M67 logical media selection

`build_selection` returns a validated copied proposal. It consumes the explicit
currently eligible M66 run and its exact ordered shot shortlists. The baseline
selects the first conservatively eligible candidate, without scoring or provider
invocation. Every planned shot has a SELECTED or UNRESOLVED outcome. Success does
not imply completeness, acquisition, canonical media, permission, timing or export
readiness. `complete(run)` derives logical completeness only.

The closed predicate preserves M66 media-kind restrictions, rejects both forms of
REFERENCE_ONLY hint, and treats other rights hints as unverified. Subject-category,
action and environment SHOW requirements require target-bound aspect MATCH
evidence for every mention. Unknown subject identity fails closed.
Non-SHOW requirement treatments, MAP/DOCUMENT/TEXTUAL representation, EXACT
identity, exact literal depiction, REQUIRED constraints (either polarity),
REQUIRED continuity, and non-generic geography/time requirements cannot be proven
by the M66 evidence vocabulary and remain unresolved. Camera scale/motion and
ordinary preferences add no hard obligations. UNKNOWN is never MATCH.

SelectionRun history is immutable through these operations. It stores references,
not descriptors. IDs and signatures use existing exact_signature; choice identity
excludes source and reviews. Immutable output includes the source, while effective
output also binds the canonical effective review projection. Review transitions
are append-only, deterministic and predecessor-bound to an exact subject. Review
changes never alter immutable run output. Hashes are integrity checks, not proof
of who authorized an action.

`append_review` requires the expected active run, exact choice and predecessor.
`replace_choice` requires the expected eligible active run, effective output,
previous exact choice and complete replacement choice. It creates a new run and
never transfers approval/lock. It has no bypass flag. Automatic regeneration
cannot replace any explicitly reviewed pending/approved or locked active subject,
even after upstream change. Rejection alone permits the explicit unresolved
review-required outcome, while a locked rejection requires creator intervention.
Rejected exact baseline choices become creator_review_required unresolved choices.
No retained inactive run is automatically reactivated.

Targeted replacement also conservatively refuses an identity collision with a
retained inactive run; restoring historical selections is not exposed here.

Historical validation uses retained retrieval/visual records; current eligibility
requires explicit pointers and exact current upstream/spec bindings. History is
never pruned. Limits are 64 runs, 4096 choices/run, 65536 total choices, 65536
review transitions and 16 diagnostic codes/run.

MediaSelectionStage is media_selection version 1. Standalone dependencies are ().
Use dependencies=("media_retrieval",) in a combined workflow. Its only artifacts,
in order, are selection/<selection_id> and selection_retrieval/<retrieval_id>.
Reuse checks the exact retained execution/artifacts, current eligibility and an
independently reconstructed automatic projection. Creator choices disable reuse.
Combined dependency signatures are reconstructed from retained upstream execution
artifacts/metadata. Reuse requires empty M62 stage configuration; nonempty
configuration conservatively rebuilds. M62 also verifies its own current inputs.

All operations check cancellation and publish only validated copied state. Every
non-selection domain must remain equal. No acquisition, external dependencies,
provider calls or canonical MediaReference changes occur. M66 aggregate scaling
and public display-text findings remain deferred. No M68 work is included.
