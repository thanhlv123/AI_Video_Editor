M125 - REAL RENDER FAILURE AND RECOVERY
======================================

Production fix
--------------
A progress callback could raise at the "prepared" phase, outside the
export transaction's exception handler, leaving its manifest stuck in
"rendering". The prepared notification and request construction now run
inside the existing backend exception-handling scope. A cancellation
records "cancelled"; other errors record "failed". Existing cleanup,
export numbering, cross-process locking and non-overwrite remain intact.

Offline acceptance
------------------
Run: python scripts/m125_render_failure_recovery.py

The test renders a disposable synthetic MP4, corrupts one source video
to force a real FFmpeg failure, checks failed status and cleanup, restores
the input, cancels at the prepared progress callback, and verifies that
the next export succeeds without altering the earlier successful MP4.
All media is temporary; no external APIs, credentials or user projects.
CI runs this after the M118 acceptance and before the full unittest suite.

Regression tests
----------------
tests/test_render_failure_recovery_m125.py verifies terminal manifests,
failure and cancellation paths, partial-output cleanup and lock release.
