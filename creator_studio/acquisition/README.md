# M68 acquisition foundation

Acquisition materializes only exact currently eligible M67 selections. It changes
only `manifest.acquisition`. Canonical media, final legal clearance, timing,
editorial trimming and rendering remain outside this domain.

Inject a trusted managed project root, registered AcquisitionProviders, an exact
AcquisitionSpec and a trusted MediaInspector. There is no network adapter or
production inspector. Missing providers yield UNSUPPORTED_SOURCE; missing inspection
fails the stage for any attempted transfer. Permission is an explicit provider
policy capability, independent of provenance rights hints. REFERENCE_ONLY is blocked.

Provider resolution receives controlled logical references from retained M66
observations. Typed public renditions are ordered by descending pixel area, width,
height, then ascending rendition ID. One rendition is transferred, with no candidate
fallback. Ephemeral opaque handles never enter persistent state. Providers receive
a bounded streaming sink with no destination API. Providers and inspectors are
trusted injected code, not sandboxed plugins; cooperative cancellation is required.
There is no hard deadline or forced interruption of a blocked adapter in this version.

Storage uses internally exclusive staging files, closes writers before inspection,
then recomputes raw SHA-256 and size. Inspection can alter bytes; only the digest
after inspection can be published. Zero bytes and bounded objective inspection
fail closed. Object keys are generated solely from digest. Installation uses an
atomic no-clobber hard link on the managed volume; unsupported filesystems fail
closed. Existing objects are fully verified and never repaired or overwritten.
“Immutable” means the acquisition API never overwrites a finalized object, not an
OS access-control guarantee against other processes. Current usability always
rehashes and reapplies trusted inspection, then rehashes again.

Managed paths reject symlinks, Windows reparse points, nonregular objects and
noncanonical keys. The managed tree and its ancestors must not be concurrently
modified by untrusted local actors: this foundation does not claim protection
against privileged hostile filesystem races. Cooperating content-object races are
supported separately from the explicit **one manifest writer per project** rule.

Objects finalize before manifest proposals. Failed publication or cancellation
may leave unreferenced complete objects. Only the current attempt's staging file
is cleaned; no garbage collection, pruning, finalized-object rollback or inactive
history reactivation occurs. History validation is pure and filesystem-free.
Current usability separately requires active exact upstream/spec bindings and
verified local bytes. Stage reuse additionally requires retained execution and
exact two ordered artifacts; incomplete coverage is derived from outcomes and is
not implied by a successful stage status.

All identities are deterministic structured signatures except raw content SHA-256.
Different candidate provenance stays separate while identical bytes share an asset.
Creator-origin choices inherit M67's rehashed trust limitation; hashes do not
authenticate a creator. Acquisition conveys no final-use approval. M67-L01/L02/L03,
M66 M-01/L-01 and M65 conservative reuse remain deferred. No failed-attempt ledger,
multiwriter manifest CAS, production provider/inspector, indexing, or M69 work.
