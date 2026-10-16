"""M127: service integration with synthetic render backend."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from creator_studio.render_backend import RenderBackendResult
from creator_studio.render_export import RenderExportService
from scripts.m118_render_acceptance import build_manifest


class FakeBackend:
    def render(self, request, *, progress_callback=None, cancel_token=None):
        request.output_path.write_bytes(b"new-video")
        return RenderBackendResult(
            success=True, output_path=request.output_path,
            video_clips=2, has_narration=True, has_music=True,
            width=320, height=180, fps=12.0,
        )


class ExportRecoveryIntegrationTests(unittest.TestCase):
    def test_retry_preserves_previous_output_and_recovers_status(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = build_manifest()
            for item in data["tracks"]["visuals"]:
                path = root / item["asset"]["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"video-placeholder")
            for role in ("narration", "music"):
                path = root / data["tracks"][role]["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"audio-placeholder")
            run = root / "work/automation/run_001"
            run.mkdir(parents=True)
            timeline = run / "timeline_manifest.json"
            timeline.write_text(json.dumps(data), encoding="utf-8")
            old = root / "exports/final_video_001.mp4"
            old.parent.mkdir(parents=True)
            old.write_bytes(b"old-user-video")
            stale = run / "render_export_manifest.json"
            stale.write_text(json.dumps({
                "format": "creator_studio.render_export.v1",
                "status": "rendering",
                "project_root": str(root),
                "output_path": str(old),
                "issues": [],
            }), encoding="utf-8")
            service = RenderExportService(
                backend=FakeBackend(), default_width=320,
                default_height=180, default_fps=12.0,
            )
            result = service.export(timeline, root)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output_path.name, "final_video_002.mp4")
            self.assertEqual(old.read_bytes(), b"old-user-video")
            self.assertEqual(json.loads(stale.read_text(encoding="utf-8"))["status"], "failed")
            self.assertEqual(json.loads(result.manifest_path.read_text(encoding="utf-8"))["status"], "completed")


if __name__ == "__main__":
    unittest.main()
