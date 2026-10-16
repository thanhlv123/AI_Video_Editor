M121 - NULLABLE NARRATION SOURCE DURATION
=========================================

Problem
-------
M113 automatic timeline assembly legitimately writes
tracks.narration.source_duration_seconds = null when voice asset metadata
has no measured duration. M114 export treated explicit null as invalid,
blocking a structurally valid ready timeline and the M120 preflight.

Fix
---
When narration source duration is absent or explicitly null, use the
positive, validated timeline duration as a metadata fallback. Do not
claim this is a measured source duration or stretch the actual audio.
Keep rejecting invalid non-null values (zero, negative, booleans,
non-numeric values, NaN, infinity). Explicit valid durations remain
unchanged. No changes to music duration handling, media assets, FFmpeg
commands, export reservation, or user project files.

Tests
-----
Regression tests in tests/test_render_export_m114.py verify null,
absent, known, invalid, and repeated non-overwriting exports.
M120 preflight tests now accept nullable narration metadata and still
reject invalid non-null values.

CI
--
M116 Windows release gate: compile, import, GUI smoke, real FFmpeg
acceptance, full unittest suite. M121 is complete only after CI passes.
