# M70 authoritative voice timing foundation

TEXT is semantic truth; exact narration bytes provide timing extent. This module
accepts explicit untrusted lexical observations; it produces no observations,
speech, transcription, alignment, edit placement, subtitle, or render output.

Use `inspect_stream` to identify imported bytes, associate their asset ID with a
read-only `NarrationByteStore`, then `register_narration` with an explicit positive
logical revision number. Identical bytes may have distinct logical revisions.
Revision provenance is closed (`UNSPECIFIED`, `USER_IMPORT`, `GENERIC_OUTPUT`).
Origin GENERATED records a declaration only. No generation or rights are proven.

`source_binding` requires explicit M64 normalized-character offsets and StoryUnit
identity. `Observation` holds runtime text only; persisted units retain token
digests and exact source spans. Digests do not anonymize short words. Matching
uses NFC, casefold, whitespace collapse, and edge Unicode punctuation removal,
versioned in AlignmentSpec. Internal punctuation, number expansions, contractions,
abbreviations and paraphrases are not fuzzy matched. EXPLICIT_VARIANT requires a
separate explicit evidence digest and gate acceptance. No missing word receives
invented timing. Omissions have source bindings but no timestamps. Added speech
has timestamps but no source binding. Coverage is recomputed over non-whitespace
source characters and is separate from acceptance and current eligibility.
The captured source-record fingerprint excludes only M63's optional source locator
so local paths cannot enter timing identity; the complete current manifest is
separately captured and rechecked around callbacks.

`build_voice_timing` requires an injected `TimingAcceptanceGate.accept(request)`.
There is no default gate. `make_receipt` is a deterministic construction utility,
not a policy or approval implementation. The deeply immutable request contains
closed frozen records, tuples, scalar signatures and canonical complete output
JSON (without raw transcript). The receipt binds the exact request, input, output,
and declared policy. Acceptance means project acceptance under that policy; it
does not authenticate a person or prove acoustic truth or final approval.

PCM_WAV_V1 accepts only little-endian RIFF/WAVE, one 16-byte PCM fmt chunk then
one data chunk, 1/2 channels, 8/16/24/32 bits and the declared supported rates.
Ancillary chunks, compressed/extensible/float WAV and other containers fail.
RIFF extent, alignment, byte rate, full payload and zero odd-byte padding are
verified. Reads are at most 1 MiB; files at most 1 GiB, durations at most 4 hours.
Microseconds use integer floor arithmetic. Frame count and sample rate retain
exact extent independently. Frame zero is time zero, including silence.

Historical validation is filesystem-, callback-, provider-, and current-pointer-
independent (except explicit pointer integrity). Changed review output does not
invalidate captured history. `current_timing_eligibility` separately reports
historical validity, rehashed audio usability, current semantic/spec/policy
bindings, explicit active pointers, and coverage. It claims no placement,
subtitle, or render readiness. Missing files can leave historical validity true.

Capture/recheck fences detect cooperating callback mutations to manifest,
observations, spec and audio; callbacks are not sandboxed and side effects are
not rolled back. Storage must cooperate: each open must return the current exact
logical asset bytes. Verification is a point-in-time check, not a filesystem lock
or guarantee against a hostile store changing bytes after the final check.
Cancellation is cooperative around bounded reads, units, bindings, validation
and callbacks; generic JSON serialization is not interruptible internally.

Only voice_timing changes in copied proposals. Histories are append-only through
these APIs, bounded at 64 assets/revisions/runs; 100k units/run, 500k total;
200k bindings/run, 1m total; 100k issues/run, 500k total; 8 bindings/unit.
Grouping segments are not implemented, so their count is always zero. No GC.
Persistent signatures detect inconsistent edits, not hostile recomputation.

`VoiceTimingStage` (voice_timing, version 1) is registered explicitly by callers
using existing orchestrator registration. Dependencies normalize once and are
only () or (semantic_story,). Reuse checks only explicit active pointers, exact
runtime observations, expected spec/policy, dependency evidence and exactly two
ordered logical artifacts: voice_timing/<run>, voice_source/<revision>.
M71 allocation and all audio producers remain deferred.
