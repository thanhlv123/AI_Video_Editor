M126 - PRODUCTION OUTPUT INTEGRITY PROBE
========================================

Real production FFmpeg exports are now checked with ffprobe before the
render export manifest can be marked completed. The probe validates the
actual MP4 container, H.264 video stream, expected resolution, AAC audio
stream, and a duration close to the timeline. The probe has a 20-second
timeout and never invokes a shell or modifies user media.

When verification fails, RenderExportService's existing error handling
marks the export manifest failed and removes the incomplete output.
Previously successful exports are not touched. Custom test backends
default to probe disabled, while production TimelineRendererBackend
defaults to enabled. verify_output=True can enable the same verification
for other backends.

Unit tests: tests/test_output_integrity_m126.py
Real acceptance: python scripts/m126_output_integrity_acceptance.py

The Windows release gate runs the real acceptance after M125 and before
the full unittest suite. External provider and GPU-specific paths still
require separate validation.
