# M63 Content Ingest

Offline standard-library implementation. `IngestRequest` requires a caller-owned
logical `content_id`; retain it when editing. `ingest()` returns a structured
success/failure. `apply_ingest()` returns a validated manifest copy; it never
changes its argument. The M62 adapter returns that copy as `ManifestUpdate`.

Readers support direct text, UTF-8 `.txt`, direct Markdown and `.md`/`.markdown`.
Reference text is direct input only. Transcript is a reserved source type with
no reader yet. Exactly one of text or local locator is accepted. No URL reader.
Files are read as bytes without newline translation, with strict UTF-8-sig
decoding. Source files are never changed. File paths are provenance only.

Original decoded text is preserved (file BOM decoding excepted). Normalization
version 1 removes one leading BOM, applies NFC, converts CRLF/CR to LF, and
removes terminal LF characters. Spaces, tabs, internal paragraph structure and Markdown
syntax remain intact; terminal LF characters and terminal blank lines are removed
from normalized_text. original_text preserves the decoded creator source. NUL, other Cc controls except tab/CR/LF, and surrogate
code points fail. Empty/whitespace-only text fails, including reference notes.
Defaults: 5 MiB encoded input and 2,000,000 characters, checked before/after
normalization; no truncation. Language is supplied or None, normalized to
lowercase hyphen-separated tags (syntax only, no detection/registry lookup).

Revision signatures use M61 `signature()` over normalized text, source type,
provenance, language, title and normalization version. Logical ID, locator,
original formatting and timestamps are excluded. Stage inputs additionally hash
the exact request/result so provenance relocation or original formatting changes
cannot reuse stale preserved data. File contents are reread and checked before
execution; changes since signature calculation fail as `source_changed`.

Manifest V2 Content adds `records` and `canonical_content_id`. Old V2 documents
receive empty defaults during migration; schema version stays 2. Existing M61
scripts remain valid with no ingest record. Canonical updates maintain the legacy
script projection, language (`und` if unknown), input kind and revision counter.
Same signature/entity does not increment the counter. No revision history is
implemented. Scene spans are validated for bounds and exact retained slice identity against
the old persisted script. Changed slices fail atomically as scene_script_span_changed
(with scene ID and offsets on IngestError); spans are never shifted or rewritten. Execution metadata is preserved.

Creator-authored, imported-owned and licensed provenance may become canonical.
Reference-only and unknown provenance cannot; use `canonical=False` to store
them as separate records. REFERENCE_TEXT always becomes reference-only. These
are content provenance states, separate from media rights. No reference scraping,
AI, semantic planning, subtitle, GUI or production pipeline integration exists.

Diagnostics contain controlled codes only, never source text, paths, exception
strings or environment values. Content itself preserves supplied text/metadata:
callers must not submit credentials as content or metadata. No environment or
credential store is read. Content Ingest supplements M62 structural artifact validation through the optional
validate_reuse stage hook. Its artifact signature fingerprints every persisted record
field plus canonical selection, script and language projections when canonical.
M61 signature() hashes ASCII-escaped JSON to retain exact original Unicode and
newline distinctions. Only fingerprints, never source text, enter execution artifacts.
Missing or changed output forces normal readiness/execution, including span protection.
