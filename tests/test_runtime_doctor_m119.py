"""M119 runtime doctor regression tests (offline and read-only)."""
import contextlib
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from creator_studio import launcher, runtime_doctor


class RuntimeDoctorTests(unittest.TestCase):
    def _diagnose(self, encoders=True):
        listing = " V....D libx264 H.264\n A..... aac AAC\n" if encoders else " V....D mpeg4 MPEG-4\n"
        with mock.patch.object(runtime_doctor.shutil, "which", side_effect=lambda name: f"C:/ffmpeg/bin/{name}.exe"):
            with mock.patch.object(runtime_doctor, "_module_available", return_value=True):
                with mock.patch.object(runtime_doctor.subprocess, "run",
                                       return_value=SimpleNamespace(returncode=0, stdout=listing, stderr="")):
                    return runtime_doctor.diagnose(environ={})

    def test_required_programs_and_codecs_ready(self):
        report = self._diagnose()
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["required_failures"], [])
        self.assertEqual(report["format"], "creator_studio.runtime_doctor.v1")

    def test_missing_faster_whisper_blocks_voice_pipeline(self):
        listing = " V....D libx264 H.264\n A..... aac AAC\n"

        def module_available(name):
            return name != "faster_whisper"

        with mock.patch.object(runtime_doctor.shutil, "which", side_effect=lambda name: f"C:/ffmpeg/bin/{name}.exe"):
            with mock.patch.object(runtime_doctor, "_module_available", side_effect=module_available):
                with mock.patch.object(
                    runtime_doctor.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stdout=listing, stderr=""),
                ):
                    report = runtime_doctor.diagnose(environ={})

        self.assertEqual(report["status"], "blocked")
        self.assertIn("faster_whisper", report["required_failures"])

    def test_missing_codecs_block_render(self):
        report = self._diagnose(encoders=False)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("h264_encoder", report["required_failures"])
        self.assertIn("aac_encoder", report["required_failures"])

    def test_missing_ffmpeg_does_not_execute_subprocess(self):
        with mock.patch.object(runtime_doctor.shutil, "which", return_value=None):
            with mock.patch.object(runtime_doctor, "_module_available", return_value=True):
                with mock.patch.object(runtime_doctor.subprocess, "run") as run:
                    report = runtime_doctor.diagnose(environ={})
        self.assertIn("ffmpeg", report["required_failures"])
        run.assert_not_called()

    def test_project_directory_check_is_read_only(self):
        with mock.patch.object(runtime_doctor.shutil, "which", return_value=None):
            with mock.patch.object(runtime_doctor, "_module_available", return_value=True):
                report = runtime_doctor.diagnose(project_root=Path("/nonexistent/project/m119"), environ={})
        self.assertIn("project_directory", report["required_failures"])

    def test_encoder_probe_timeout_is_reported(self):
        with mock.patch.object(runtime_doctor.subprocess, "run", side_effect=subprocess.TimeoutExpired("ffmpeg", 10)):
            h264, aac, note = runtime_doctor._encoders("ffmpeg")
        self.assertFalse(h264)
        self.assertFalse(aac)
        self.assertEqual(note, "TimeoutExpired")

    def test_doctor_command_reports_blocking_status(self):
        with mock.patch.object(runtime_doctor, "diagnose",
                               return_value={"status": "blocked", "required_failures": ["ffmpeg"]}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = launcher.main(["--doctor"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["required_failures"], ["ffmpeg"])

    def test_doctor_command_reports_success(self):
        with mock.patch.object(runtime_doctor, "diagnose",
                               return_value={"status": "ready", "required_failures": []}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = launcher.main(["--doctor"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "ready")


if __name__ == "__main__":
    unittest.main()
