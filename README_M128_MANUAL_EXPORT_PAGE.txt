M128 - MANUAL EXPORT PAGE
=========================

The Creator Studio "Xuất video" page is now functional rather than a
placeholder. It discovers completed M113 timeline manifests in the
currently selected project's work/automation/run_* folders.

The user can select a ready run, request an MP4 render, watch progress,
cancel a running render, open the finished video, or open its export folder.
Rendering uses the existing RenderExportService and its M124 readiness
gate, M123 cross-process project lock, M125 failure recovery, M126 MP4
integrity checks, and M127 interrupted-export reconciliation.

Rendering runs in a QThread so the interface remains responsive.
The main window refuses to close while manual export is active. Existing
MP4s are never overwritten; each export reserves a new numbered filename.
Project files are not changed by timeline discovery.

The automatic one-click render path remains unchanged. This milestone
adds a separate manual re-export workflow without modifying the timeline
engine, provider APIs, or existing render manifest format.

Tests:
  tests/test_manual_export_m128.py
  tests/test_manual_export_gui_m128.py

Acceptance:
  Windows release gate: production GUI smoke, FFmpeg acceptance,
  import discovery, and full unittest suite.
