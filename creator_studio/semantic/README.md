# M64 text-first semantic story foundation

This standard-library-only package turns current eligible M63 canonical content
into revision-bound structural blocks and conservative StoryUnits. It performs no
AI inference, media operations, network access, scene generation or timing work.

`build_semantic_story(manifest)` returns a fully validated copied proposal. Input,
archive insertion, documents and selection are unchanged on failure/cancellation.
Analyzer inputs and results are isolated copies. `SemanticAnalyzer` returns typed
candidates without authoritative IDs; the engine assigns IDs and validates every
evidence string. Analyzer exceptions become controlled codes without payloads.

Plain mode groups contiguous ordinary LF-separated lines into paragraphs.
Markdown mode derives from SourceType.MARKDOWN or explicit StructuralOptions.
Precedence is fences, ATX headings, conservative tables, list items and clearly
indented continuations, quotes, explicitly dash-and-quotation-mark dialogue, then
paragraphs. Arbitrary Name: text remains prose. Markers and internal whitespace
stay in slices; whitespace-only separators may remain uncovered. Fences are
opaque; unclosed fences consume the remainder and warn. No sentence splitting or
truncation occurs. Structural scanning uses line offsets, never substring search.

The baseline emits one full-block unit per prose-bearing block, excluding
headings, tables and code. Annotations stay empty, visualizability UNKNOWN and
confidence absent. StoryUnits are evidence contracts, never production scenes.

SemanticStoryStage registers one M62 stage, semantic_story, version 1. Pass
dependencies=("content_ingest",) for a combined workflow or use the empty default
for already-ingested content. No orchestrator internals change. Its artifact holds
only deterministic references and fingerprints, never source text. Reuse checks
canonical eligibility, the complete persistent state, effective specification,
selected output fingerprint and fresh baseline equality. Future non-baseline
analyzers conservatively receive no reuse until an offline validation policy is
defined. AnalysisOptions is deliberately empty: the baseline has no analysis
configuration; every exposed structural option is executed and signed.

Review fields are outside generated document identity but inside output
fingerprints. Explicit rebuild preserves review metadata for an existing exact
document ID. There is no override merging. Reuse refuses reviewed/modified output
when it differs from the generated baseline. Historical revisions are never
deleted or automatically selected. No persisted stale boolean exists.

All spans are zero-based Python Unicode code-point intervals [start, end), with
strict integer boundaries (not bool/float), nonempty and in bounds. Every stored
excerpt and mention must equal the exact retained normalized_text slice. Qt and
JavaScript clients must convert UTF-16 positions before using this contract.
Combining marks and ZWJ sequences do not change indexing to grapheme positions.

Signature construction reuses M61 signature(), preceded by deterministic ASCII
JSON serialization to preserve exact Unicode distinctions. Source revision IDs
bind logical content ID, M63 revision and contract version. Structural identity
binds revision, exact normalized text, normalization version, segmenter and
effective options. Analysis binds structure, complete specification and purpose.
Block/unit/document IDs have deterministic type prefixes. Output signatures cover
all persisted document fields except output_signature itself. No time, temporary
path, UUID, execution attempt, voice or duration enters generated identity.

The archive preserves the first originating persisted ContentRecord plus an exact
record fingerprint for each logical ID/revision. Original formatting and locators
are evidence, not semantic identity inputs. M63 remains canonical authority; an
archived record cannot promote itself to creator content. A current source change
leaves historical spans intact and makes the old selection ineligible. Returning
to an older revision does not select an older document automatically.

M64 intentionally defers semantic inference, chunking, provider adapters, visual
planning, GUI, voice and timing, reference ingestion and human override merging.

H1 exact archive reuse binding: execution emits a document artifact binding the
source revision ID, exact retained source_signature, document ID, output fingerprint
and analysis identity, plus a semantic_source artifact exposing only the revision
ID and exact fingerprint. Missing legacy bindings or changed original formatting,
locator or any other retained record field invalidate reuse even when M63 semantic
revision identity stays unchanged. Valid changed archives are revalidated through
normal execution, not classified as manifest corruption. No raw text is emitted.

H2 automatic replacement policy: APPROVED document review, APPROVED unit review,
or any unit ReviewMetadata.locked protects the active creator document. There are
no independent annotation review/lock fields or document locks in this contract;
unit review metadata supplies the existing lock. Unlocked PENDING or REJECTED
state alone does not protect replacement. A different generated document ID is
blocked with semantic_review_required (FAILED, non-retryable, no update/artifacts).
The copied proposal is discarded, preserving canonical content, source archive,
documents, selection and reviews atomically. Same-ID builds preserve reviews and
locks. Configuration changes invalidate reuse before this guard is evaluated.
No proposal selection or replacement override workflow is introduced.
