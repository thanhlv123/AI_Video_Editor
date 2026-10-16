M130 - EXPORT HISTORY UI
========================

The manual "Xuất video" page now shows completed MP4 exports for the current
project. Users can refresh the read-only history, select an export, open its
video, or open its folder. The list refreshes after successful manual exports
and clears when switching projects. Rendering itself is unchanged.

M129 discovery now sorts newest manifests first, deduplicates output paths,
and rejects symlinked run directories and output files, empty files,
non-MP4 paths, relative paths, and files outside the project's exports
directory. Windows 8.3 aliases are handled using filesystem identity.

The UI never deletes or overwrites project files. Existing automated
one-click export and manual re-export remain separate and unchanged.

Relevant tests:
  python -m unittest tests.test_export_history_m129
  python -m unittest tests.test_export_history_safety_m129
  python -m unittest tests.test_export_history_hardening_m130
  python -m unittest tests.test_export_history_gui_m130
  python -m unittest tests.test_manual_export_gui_m128

Acceptance gate:
  Windows Python 3.12 compile/import, GUI smoke, real FFmpeg acceptance,
  and full unittest suite in .github/workflows/m116-release-gate.yml.
