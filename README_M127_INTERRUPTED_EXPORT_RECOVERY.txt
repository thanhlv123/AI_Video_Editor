M127 - INTERRUPTED EXPORT RECOVERY
==================================

A crash or forced shutdown can leave a render_export_manifest*.json in
"rendering" indefinitely. On the next export in the same timeline run,
Creator Studio now reconciles stale manifests under the existing
cross-process project export lock.

A stale manifest becomes status=failed with issue render_interrupted and
an actionable explanation. All existing MP4s and project media remain
untouched, including an occupied output filename. The new export selects
the next available numbered MP4 and a separate export manifest.

Completed, failed, cancelled, malformed, foreign-project, and unknown-format
manifests are ignored. Replacement of valid manifest JSON is atomic.
Individual recovery I/O errors do not prevent subsequent exports.

Tests: tests/test_export_recovery_m127.py
       tests/test_export_recovery_integration_m127.py
Acceptance: python scripts/m127_interrupted_export_acceptance.py

The Windows release gate runs real FFmpeg acceptance and the full suite.
Recovery is limited to the selected timeline run directory.
