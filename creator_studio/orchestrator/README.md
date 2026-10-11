# M62 execution contracts

Repository saves are the persistence boundary. PersistenceAbort carries a controlled
project-level diagnostic, boundary, stage ID and attempt; callers must surface it.
It aborts scheduling immediately, without a fallback write or fabricated stage failure.
Copy/validate/save keeps the last acknowledged manifest unchanged on failed saves.
A storage backend that writes and then raises has an uncertain durable outcome;
reload/recovery is required before another run. Raw exceptions are never copied into
results or diagnostic payloads.

_execute owns all executed-attempt result saves, including retries and terminal
results. _run saves only non-executed results. Invalid proposals are rejected before
saving and replaced by a controlled failure retaining the attempt number.

Optional M62 execution records must agree with enclosing processing identity,
status and any enclosing signature. READY/BLOCKED map to PENDING; SKIPPED maps to
SUCCEEDED; all other statuses map directly. An absent enclosing signature is allowed
for compatibility. Reuse requires enclosing SUCCEEDED, nested SUCCEEDED/SKIPPED,
matching identity, registered version, current signature and valid artifacts.
A different registered version invalidates reuse; it does not invalidate old history.
M61 records without execution remain loadable and cannot authorize reuse.

Preflight rejects duplicate processing mappings for registered stages and changed
live stage declarations before any project-status write. Duplicate legacy stage names
remain valid M61 documents. Frozen registration descriptors govern graph order and
execution identity. The registry is exposed read-only and registration is locked
throughout execution. Live declarations are checked before the run and each stage.

READY permits execution. SATISFIED alone cannot prove reusable output. NOT_READY
remains PENDING and emits STAGE_PENDING; BLOCKED emits STAGE_BLOCKED. In this
synchronous foundation any incomplete stage makes the project FAILED; no deferred
scheduler is implied.

Cancellation requested before a run applies to that run. Every completed or aborted
active run installs a fresh token, so a cancelled instance can be reused. Engines
must not retain contexts across runs.

Engines must never include secrets in results. Exception conversion uses fixed codes
and messages, never provider exception text, headers or environment dumps. Credential
pattern rejection is defense in depth, not proof that arbitrary payloads are safe.

Checkpoint registration failure raises PersistenceAbort with checkpoint_path so the
recovery file is explicitly discoverable. Existing checkpoint destinations are refused.

Declaration consistency has one owner: StageGraph.preflight compares live stage_id,
stage_version and dependencies against frozen registration descriptors. It runs at
initial/stage preflight, after observer callbacks, after signature_inputs/readiness,
before each attempt and immediately before/after execute (including exceptional
returns). Result acceptance follows this check. Frozen descriptors supply all
signature and execution identity fields; live engines supply implementation only.

StageDeclarationError carries stage_declaration_changed, the registered ID and a
fixed field name. It propagates beyond engine handlers, stops all scheduling and
never becomes a retry result. Proposed outputs are discarded. No abort write is
attempted: the last acknowledged project/attempt record remains available for
recovery, possibly RUNNING. Prior completed attempts retain their accurate counts.
Controllers must surface the exception and reload before recovery. PersistenceAbort
behavior and observer exception isolation remain unchanged.
