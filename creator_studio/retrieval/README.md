# M66 Media Retrieval Foundation

This package discovers bounded candidate metadata from eligible M65 structured
visual requirements. It does not select, acquire, inspect files, create canonical
media, or modify scenes. Production defaults to `OfflineEmptyProvider`; positive
synthetic providers exist only in tests. No network, filesystem, GUI, AI, stock,
probe, or renderer dependency is used by the runtime.

`build_retrieval(manifest, providers=None, spec=None, control=None,
required_visual_spec=None, required_semantic_spec=None)` returns a copied,
validated proposal. `providers=None` means the production offline provider;
an empty collection is unavailable. Cancellation raises M62 `Cancelled` and
failures raise a controlled `RetrievalError`. No failed attempt publishes a run.
Providers receive copied typed requests and cooperative cancellation control.
Metadata getters, capability copies, response copies, and calls are guarded.

Requests project structured M65 fields without narration, translation, inferred
terms, or provider syntax. Preferred forms restrict kinds without substitution;
UNKNOWN fields do not loosen hard constraints. All-UNKNOWN requirements produce
INSUFFICIENT_INTENT without provider invocation. Explicit requests can yield
EMPTY, UNSUPPORTED, FAILED, or CANDIDATES. All attempted providers failing aborts;
valid successful invocations permit a completely validated partial run with a
warning. Empty discovery never means selection is ready.

Providers declare public ID/version/catalog namespace, source class, supported
visual kinds, structured-intent support, and request limit. Effective limits are
the minimum of provider and global limits. The complete typed RetrievalSpec,
including ordered provider descriptors and source precedence, is signed. There
is no arbitrary config dictionary or credential hash. Provider metadata errors
make readiness unavailable; call/batch failures produce controlled outcomes.

Candidates are discovery-only descriptors. Their logical identity signs version,
provider ID, captured catalog namespace and a public namespaced reference such as
`video:123` (candidate identity contract version 2). Provider version and descriptive
metadata are excluded from logical identity. Historical candidates validate against
their captured namespace and captured provider spec, independently of today's catalog.
The namespace is also signed by metadata, generated-result, run, output and artifact
signatures through the existing exact-signature chain.

Public references use ASCII `<namespace>:<identifier>`: namespace starts with a
letter, contains letters/digits/underscore/hyphen, and is 2?24 characters (single
letters are excluded to prevent Windows drive forms). Identifier starts with an
alphanumeric, contains letters/digits/underscore/hyphen/dot, and is 1?48 characters.
Nested colons, whitespace, escapes, URL/path punctuation and reserved locator schemes
are excluded. Catalog namespaces separately start with a letter, allow ASCII
letters/digits/underscore/hyphen/dot, and are at most 48 characters. Explicit
credential marker prefixes are rejected in both contracts; this is a narrow public
identifier contract, not arbitrary secret detection. Display text retains its
separate existing validation.
Metadata fingerprints sign the allowlisted descriptor without identity/digest
fields. Same logical assets may appear in multiple shot shortlists; contradictory
observations reject the invocation rather than merge metadata. Cross-provider
identity is distinct. No content similarity deduplication is attempted.

Evidence belongs to a shot-candidate relationship: aspect, finding, method,
version, optional exact M65 mention reference. Known conflicts are conservatively
filtered, including conflicts on preferences. Unknown observations stay
UNVERIFIED; REFERENCE_ONLY remains independent of permissive Rights hints.
Discovery never establishes final eligibility or authoritative provenance.

Ordering uses signed source precedence, signed provider order, discovery
position, then candidate ID. Calls are sequential; completion timing cannot
change order. Canonical descriptor storage sorts by candidate ID. Signed per-shot
truncation is stable and diagnosed. Exceeding unique/run/history ceilings fails
without pruning. Defaults: 32 proposals per provider/shot, 8 persisted per shot,
1024 unique per run. Hard ceilings: 128 proposals, 32 per shortlist, 4096 unique
per run, 4096 shots/run, 16 providers, 64 evidence items/candidate/shot, 16
diagnostics/list, 64 runs, 16384 historical candidates, 65536 historical shot
results. Public strings are bounded to 256 characters (identifiers: 128).

Identity layers use existing `exact_signature`: exact upstream binding, input
fingerprint, retrieval spec signature, request signature, logical candidate ID,
metadata observation digest, generated result digest, run ID, output signature.
Different results for the same request have different run IDs. Identical results
reuse the existing run identity without deleting history. Eligibility is derived
from the explicitly active run and current upstream/spec state; it never changes
the active ID. Visual review changes preserve historical validity and stale the
captured output signature.

The upstream binding includes VisualPlan ID/output, semantic document ID/output,
analysis signature, content revision, retained source revision and independently
recomputed exact retained ContentRecord fingerprint. Stage input additionally
binds the current canonical record fingerprint: normalized-identical formatting
or locator changes invalidate M62 execution reuse without rewriting retained
semantic evidence. Historical validation checks the captured source chain.

`MediaRetrievalStage` has ID `media_retrieval`, version `1`, standalone dependencies
`()`, optionally `("visual_director",)`. Its exact artifacts, in order, are
`retrieval/<retrieval_id>` and `retrieval_visual/<visual_plan_id>`; payloads contain
only IDs/digests. M62 owns dependency/configuration signature comparison. The
stage additionally checks retained execution, whole-manifest validity, current
spec/output/binding, active run, all identities/references and exact artifacts.
Standalone default-configuration signatures are also independently recomputed.
Nondefault standalone orchestrator configuration conservatively disables reuse.

Only exact production OfflineEmptyProvider identity/configuration permits
automatic reuse, with independently regenerated expected output. Custom and
future live providers default to no reuse. No TTL, refresh, random identity,
clock, or provider hash is treated as authenticity. Future live discovery must
define its own trusted observation/reuse policy.

Future library/project providers can expose stable logical virtual-shot IDs;
their paths, source bounds, relocation and usage systems remain outside M66.
There is no candidate approval, selection, resolver or acquisition workflow here.

Existing M65 automatic-reuse recomputation clears visual history on a temporary
manifest. Once retrieval history references it, whole-manifest validation rejects
that temporary state and M65 safely executes again instead of skipping. Combined
workflows still succeed, preserve retrieval history and reuse M66 when its exact
inputs match. This conservative upstream reuse limitation is left unchanged
because M66 does not modify visual runtime modules.

Run offline verification with `python -m unittest tests.test_media_retrieval -v`.

Blocker boundary corrections: every provider metadata exception, including a
provider-raised RetrievalError, becomes retrieval_provider_unavailable. Invocation
failures remain retrieval_provider_failed. Provider exception messages/args/codes
are never persisted. Stage diagnostics and unavailable signature inputs independently
normalize unexpected codes using the central diagnostic allowlist; valid internal
codes are preserved.

Deferred review findings: M-01 aggregate manifest scale and L-01 broad display-text
filtering remain unchanged in this blocker-only pass.
