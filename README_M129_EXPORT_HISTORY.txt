M129 Export History Foundation
==============================

This milestone adds a read-only way to discover completed video exports
from a Creator Studio project. It reads existing render_export_manifest
records and returns only nonempty files in the selected project's exports
directory. No existing project file is modified.

Usage from the repository root:
  python -m scripts.m129_export_history "C:\\path\\to\\project"

This is a backend/CLI foundation. Integration into the Manual Export GUI
and stricter manifest validation remain separate follow-up work.

Tests:
  python -m unittest tests.test_export_history_m129
  python -m unittest tests.test_export_history_safety_m129
