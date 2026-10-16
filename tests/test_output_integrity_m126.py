"""M126: ffprobe output integrity and export failure persistence."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from creator_studio.output_integrity import OutputIntegrityError, verify_rendered_output
from creator_studio.render_backend import RenderBackendResult
from creator_studio.render_export import RenderExportError, RenderExportService
from scripts.m118_render_acceptance import build_manifest


def _metadata(*, video=True, audio=True, width=320, height=180, duration="2.0"):
    streams = []
    if video:
        streams.append({
            "codec_type": "video", "codec_name": "h264",
            "width": width, "height": height,
        })
    if audio:
        streams.append({"codec_type": "audio", "codec_name": "aac"})
    return {"streams": streams, "format": {"duration": duration}}


class OutputIntegrityProbeM126Tests(unittest.TestCase):
    def _probe(self, payload, *, returncode=0):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "video.mp4"
            path.write_bytes(b"synthetic-container")
            completed = subprocess.CompletedProcess(
                ["ffprobe"], returncode, stdout=json.dumps(payload), stderr=""
            )
            with patch(
                "creator_studio.output_integrity.subprocess.run",
                return_value=completed,
            ) as run:
                result = verify_rendered_output(
                    path, expected_width=320, expected_height=180,
                    expected_duration=2.0, ffprobe="ffprobe",
                )
                self.assertFalse(run.call_args.kwargs.get("shell", False))
                self.assertEqual(run.call_args.kwargs["timeout"], 20)
                return result

    def test_valid_h264_aac_streams_pass(self):
        result = self._probe(_metadata())
        self.assertEqual(result["format"]["duration"], "2.0")

    def test_missing_audio_is_rejected(self):
        with self.assertRaisesRegex(OutputIntegrityError, "AAC audio"):
            self._probe(_metadata(audio=False))

    def test_wrong_resolution_is_rejected(self):
        with self.assertRaisesRegex(OutputIntegrityError, "resolution"):
            self._probe(_metadata(width=640))

    def test_invalid_duration_is_rejected(self):
        with self.assertRaisesRegex(OutputIntegrityError, "duration"):
            self._probe(_metadata(duration="NaN"))

    def test_bad_container_is_rejected(self):
        with self.assertRaisesRegex(OutputIntegrityError, "container"):
            self._probe(_metadata(), returncode=1)

    def test_ffprobe_timeout_is_actionable(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "video.mp4"
            path.write_bytes(b"x")
            with patch(
                "creator_studio.output_integrity.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["ffprobe"], 20),
            ):
                with self.assertRaisesRegex(OutputIntegrityError, "TimeoutExpired"):
                    verify_rendered_output(
                        path, expected_width=320, expected_height=180,
                        expected_duration=2.0, ffprobe="ffprobe",
                    )


class _SyntheticBackend:
    def render(self, request, *, progress_callback=None, cancel_token=None):
        request.output_path.write_bytes(b"synthetic-mp4")
        return RenderBackendResult(
            success=True, output_path=request.output_path,
            video_clips=2, has_narration=True, has_music=True,
            width=320, height=180, fps=12.0,
        )


class OutputIntegrityServiceM126Tests(unittest.TestCase):
    def _fixture(self, root):
        manifest = build_manifest()
        for item in manifest["tracks"]["visuals"]:
            relative = item["asset"]["path"]
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"video-placeholder")
        for role in ("narration", "music"):
            path = root / manifest["tracks"][role]["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"audio-placeholder")
        timeline = root / "work/automation/run_test/timeline_manifest.json"
        timeline.parent.mkdir(parents=True, exist_ok=True)
        timeline.write_text(json.dumps(manifest), encoding="utf-8")
        return timeline

    def test_probe_failure_marks_export_failed_and_cleans_partial_mp4(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = self._fixture(root)
            service = RenderExportService(
                backend=_SyntheticBackend(), verify_output=True,
                default_width=320, default_height=180, default_fps=12.0,
            )
            with patch(
                "creator_studio.render_export.verify_rendered_output",
                side_effect=OutputIntegrityError("No valid video stream."),
            ) as probe:
                with self.assertRaisesRegex(RenderExportError, "No valid video"):
                    service.export(timeline, root)
            probe.assert_called_once()
            report = json.loads(
                (timeline.parent / "render_export_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["status"], "failed")
            self.assertFalse((root / "exports/final_video_001.mp4").exists())

    def test_explicit_probe_acceptance_completes_export(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = self._fixture(root)
            service = RenderExportService(
                backend=_SyntheticBackend(), verify_output=True,
                default_width=320, default_height=180, default_fps=12.0,
            )
            with patch(
                "creator_studio.render_export.verify_rendered_output",
                return_value=_metadata(),
            ) as probe:
                result = service.export(timeline, root)
            self.assertEqual(result.status, "completed")
            probe.assert_called_once()
            self.assertTrue(result.output_path.is_file())


if __name__ == "__main__":
    unittest.main()
