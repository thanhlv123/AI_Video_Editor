"""M125: callback failures at the prepared phase must finalize export state."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from creator_studio.export_lock import project_export_lock
from creator_studio.render_backend import RenderBackendCancelled
from creator_studio.render_export import RenderExportError, RenderExportService


class _NeverRenderBackend:
    def render(self, request, *, progress_callback=None, cancel_token=None):
        raise AssertionError("Renderer should not run after prepared callback failure.")


class RenderFailureRecoveryM125Tests(unittest.TestCase):
    def _check_failure(self, error, expected_exception, expected_status):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = root / "work" / "automation" / "run_test" / "timeline_manifest.json"
            timeline.parent.mkdir(parents=True)
            timeline.write_text('{"status":"ready"}', encoding="utf-8")
            prepared = SimpleNamespace(
                project=SimpleNamespace(
                    settings=SimpleNamespace(width=320, height=180, fps=12.0)
                ),
                duration_seconds=2.0,
                visual_clip_count=1,
                has_narration=True,
                has_music=False,
            )
            service = RenderExportService(backend=_NeverRenderBackend())
            observed = []

            def on_progress(event):
                observed.append(event.phase)
                if event.phase == "prepared":
                    raise error

            with patch.object(service, "_prepare_render", return_value=prepared):
                with self.assertRaises(expected_exception):
                    service.export(timeline, root, progress_callback=on_progress)

            manifest_path = timeline.parent / "render_export_manifest.json"
            self.assertTrue(manifest_path.is_file())
            report = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], expected_status)
            self.assertTrue(report["error"])
            self.assertEqual(report["issues"], [
                "render_cancelled" if expected_status == "cancelled" else "render_failed"
            ])
            self.assertEqual(observed, ["validating", "prepared"])
            self.assertFalse((root / "exports" / "final_video_001.mp4").exists())
            with project_export_lock(root):
                pass

    def test_prepared_progress_handler_error_is_recorded(self):
        self._check_failure(
            RuntimeError("UI progress handler failed"),
            RenderExportError,
            "failed",
        )

    def test_prepared_callback_cancellation_is_recorded(self):
        self._check_failure(
            RenderBackendCancelled("User cancelled during preparation"),
            RenderBackendCancelled,
            "cancelled",
        )


if __name__ == "__main__":
    unittest.main()
