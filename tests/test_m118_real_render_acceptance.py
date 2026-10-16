"""M118 deterministic tests for the real-render acceptance harness."""

import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import m118_render_acceptance as acceptance


class RealRenderAcceptanceContractTests(unittest.TestCase):
    def test_fixture_manifest_is_ready_and_uses_relative_media_paths(self):
        manifest = acceptance.build_manifest()
        self.assertEqual(manifest["status"], "ready")
        self.assertEqual(manifest["duration_seconds"], 2.0)
        tracks = manifest["tracks"]
        paths = [
            tracks["narration"]["path"],
            tracks["music"]["path"],
            *(item["asset"]["path"] for item in tracks["visuals"]),
        ]
        self.assertEqual(len(paths), 4)
        for path in paths:
            self.assertFalse(Path(path).is_absolute())
            self.assertFalse(".." in Path(path).parts)

    def test_fixture_visuals_cover_narration_without_gaps(self):
        visuals = acceptance.build_manifest()["tracks"]["visuals"]
        self.assertEqual(len(visuals), 2)
        self.assertEqual(visuals[0]["start_seconds"], 0.0)
        self.assertEqual(visuals[0]["end_seconds"], visuals[1]["start_seconds"])
        self.assertEqual(visuals[1]["end_seconds"], 2.0)

    def test_failed_ffmpeg_command_reports_stderr(self):
        completed = SimpleNamespace(returncode=1, stderr="synthetic codec failure", stdout="")
        with mock.patch.object(acceptance.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "synthetic codec failure"):
                acceptance._run_command(["ffmpeg", "-version"])

    def test_cli_reports_success_as_json(self):
        with mock.patch.object(acceptance, "run_acceptance", return_value={"status": "passed"}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = acceptance.main([])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "passed")

    def test_cli_returns_nonzero_and_json_when_runtime_missing(self):
        with mock.patch.object(acceptance, "run_acceptance", side_effect=RuntimeError("ffprobe missing")):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                code = acceptance.main([])
        self.assertEqual(code, 1)
        self.assertIn("ffprobe missing", json.loads(output.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
