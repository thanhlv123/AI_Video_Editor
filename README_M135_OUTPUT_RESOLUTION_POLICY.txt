M135 - OUTPUT RESOLUTION POLICY
===============================

Real Windows acceptance found that selecting 16:9 + 1080p could still export a
2048x1080 video because the render layer inherited the first source asset's
resolution whenever the timeline policy did not declare explicit dimensions.

M135 makes the one-click automation configuration authoritative for render
resolution:
- 16:9 1080p -> 1920x1080
- 16:9 720p  -> 1280x720
- 9:16 1080p -> 1080x1920
- 9:16 720p  -> 720x1280
- 1:1 1080p  -> 1080x1080
- 1:1 720p   -> 720x720

The generic/manual RenderExportService keeps its prior source-asset fallback
unless the caller explicitly enables preferred output settings, preserving
existing behavior outside one-click automation.

Regression coverage verifies that a 2048x1080 first asset no longer overrides
the user's 16:9 1080p selection in automatic rendering.
