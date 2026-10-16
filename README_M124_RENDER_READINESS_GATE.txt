M124 – Mandatory render readiness gate

Before the automated render starts, the UI-neutral coordinator now runs the
read-only M120 timeline preflight. Missing or empty media, invalid timeline
contracts, and invalid manifests fail the render stage with actionable
diagnostics before the FFmpeg backend is called. Non-fatal warnings do not
block export. The cancellation token is checked on both sides of preflight.

The existing render/export service still independently validates assets.
This gate does not change the project, timeline, export numbering or renderer.
Tests cover successful readiness, warnings, bounded diagnostics, missing
visuals, failure persistence and no backend/output on blocked timelines.
