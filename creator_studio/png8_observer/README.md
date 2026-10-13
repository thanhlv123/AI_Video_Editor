# M80 PNG8 structural preflight runtime

`PNG8PreflightRuntime().preflight(runtime, snapshot)` performs actual
application-controlled structural execution. Both inputs must be exact M77
`SourceSnapshotRuntime` / `VerifiedSourceSnapshot` objects. It calls the supplied
runtime's public `snapshot_bytes(snapshot)` before reading and publicly validating
the descriptor, checks exact built-in bytes and byte-count agreement, and parses
those immutable bytes directly. Foreign, released and unregistered capabilities
fail closed. No source path is reopened or rehashed. The caller retains snapshot
ownership and responsibility for M77 release; M80 never releases it.

The fixed M79 V1 method spec is constructed and publicly validated internally.
There are no caller-selected methods, limits, parser callbacks or CRC providers.
The grammar is exactly signature, IHDR, pHYs, IDAT+, IEND, EOF. The signature is
`89 50 4E 47 0D 0A 1A 0A`. Each chunk has a four-byte unsigned big-endian length,
four-byte type, payload and four-byte unsigned big-endian stored CRC. At least
12 bytes must remain and payload bounds are checked before offset calculation.
Every CRC uses `zlib.crc32(view) & 0xFFFFFFFF` over contiguous type plus payload,
excluding length and stored CRC. Temporary memoryviews are released in finally.

IHDR is first, unique and exactly 13 bytes. Width and height must be positive,
at most 4096 each and at most 4,000,000 pixels in product. Only bit depth 8 with
color types 0 (L), 2 (RGB), 4 (LA), 6 (RGBA) is accepted. Compression, filter and
interlace methods must all be zero. pHYs immediately follows IHDR, is unique and
exactly nine bytes: X and Y must be positive and equal; unit must be zero. Exact
X/Y/unit values are preserved, without deriving DPI or physical dimensions.

One or more consecutive IDAT chunks must have positive aggregate payload size.
Individual zero-length IDAT chunks are allowed. Payloads are neither retained,
concatenated nor decompressed. IEND must have length zero, pass CRC, follow IDAT
and end exactly at EOF. All other chunks, including metadata, palettes,
transparency, animation and unknown/private chunks, are rejected.

Resource limits are inherited from M79: 33,554,432 input bytes, 4096 per coded
axis and 4,000,000 coded pixels. The final encoded profile uses the public M79
model and validator. One concurrent execution is admitted per runtime through
a nonblocking lock; another returns RESOURCE_LIMIT_EXCEEDED before M77 access.
No global registry, outstanding result or retained snapshot exists.

The fixed 30-second monotonic cooperative deadline starts upon admission.
Checkpoints surround byte acquisition and CRC work, occur each chunk, before
profile validation and before returning success. This is not a hard wall-clock
guarantee: native CRC work cannot be interrupted mid-call. Deadline checkpoints
immediately after admission and acquisition precede subsequent input validation
as required by the cooperative deadline model. Otherwise failure precedence is
types, gate, M77 access, descriptor, bytes/count, size, fixed method, signature,
chunk bounds/order/length/CRC/semantics, EOF, aggregate IDAT, profile, result.

Failures contain only a closed code, with absent descriptor and profile:
SNAPSHOT_AUTHORITY_INVALID, UNSUPPORTED_FORMAT, STRUCTURAL_INVALID,
RESOURCE_LIMIT_EXCEEDED, DEADLINE_EXCEEDED or INTERNAL_FAILURE. MemoryError
attempts a resource failure; if that allocation fails it propagates. Ordinary
unexpected exceptions become INTERNAL_FAILURE; BaseException is not swallowed.
The gate resets in finally, and local byte/view references are dropped.
Detached validation uses the fixed error `png8_preflight_result_invalid`.

No Pillow or other dependency is needed. There is no decompression or raster
decode. Header-valid compressed garbage may pass. Success establishes neither
pixel validity, effective opacity, renderer compatibility nor executability.
It produces no M76 physical observation claim, M78 SUCCEEDED/COMPLETE execution,
live observation authority, M75 presentation compliance or M73 blocker discharge.
There is no Manifest integration or persistence.

Results are frozen detached records containing only outcome, validated M77
descriptor, validated M79 profile and failure code according to outcome. No source
bytes, memoryviews, paths, chunks, metadata, diagnostics or raw exceptions are
retained. The public result validator verifies exact record/enum types and
success/failure combinations through the public M77 and M79 validators.

A successful invocation reports that M80 actually performed preflight over live
M77 bytes. Possession, copy, deepcopy, serialization or manual reconstruction of
its detached result does not prove execution occurred and grants no authority.
A future trusted observer MUST rerun preflight itself and MUST NOT accept a
caller-supplied M80 result as trusted evidence. Preflight does not complete M79.
