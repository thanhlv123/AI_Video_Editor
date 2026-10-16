"""M131 Windows bootstrap regression tests; no packages are installed."""
from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import m131_bootstrap as bootstrap


class BootstrapTests(unittest.TestCase):
    def test_check_is_read_only_and_reports_prerequisites(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            report = bootstrap.inspect_environment(root)
            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["checks"]["local_environment"])
            self.assertFalse((root / ".venv").exists())

    def test_check_cli_never_calls_install(self):
        fake = {"status": "ready", "checks": {}}
        with patch.object(bootstrap, "inspect_environment", return_value=fake):
            with patch.object(bootstrap, "install_environment", side_effect=AssertionError("unexpected install")):
                with patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(bootstrap.main(["--check"]), 0)
                    self.assertEqual(json.loads(output.getvalue()), fake)

    def test_incomplete_existing_environment_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements-runtime.txt").write_text("PyQt6>=6.7\n", encoding="utf-8")
            (root / ".venv").mkdir()
            with patch.object(bootstrap.subprocess, "run", side_effect=AssertionError("unexpected process")):
                self.assertEqual(bootstrap.install_environment(root), 1)

    def test_install_uses_local_python_and_preserves_existing_project_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements-runtime.txt").write_text("PyQt6>=6.7\n", encoding="utf-8")
            project = root / "projects" / "my_project.txt"
            project.parent.mkdir()
            project.write_bytes(b"important user data")
            python = bootstrap.environment_python(root)
            commands = []

            def fake_run(argv, **kwargs):
                commands.append(argv)
                if len(commands) == 1:
                    python.parent.mkdir(parents=True)
                    python.write_bytes(b"fake python")
                return SimpleNamespace(returncode=0)

            with patch.object(bootstrap.subprocess, "run", side_effect=fake_run):
                self.assertEqual(bootstrap.install_environment(root), 0)
            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[0][1:3], ["-m", "venv"])
            self.assertEqual(commands[1][:4], [str(python), "-m", "pip", "install"])
            self.assertEqual(project.read_bytes(), b"important user data")

    def test_ready_when_packages_and_ffmpeg_are_present(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            python = bootstrap.environment_python(root)
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fake python")
            with patch.object(bootstrap, "probe_runtime_packages", return_value=True):
                with patch.object(bootstrap.shutil, "which", return_value="C:/ffmpeg/bin/ffmpeg.exe"):
                    report = bootstrap.inspect_environment(root)
            self.assertTrue(report["checks"]["local_environment"])
            self.assertTrue(report["checks"]["runtime_packages"])
            self.assertTrue(report["checks"]["ffmpeg"])
            self.assertTrue(report["checks"]["ffprobe"])

    def test_windows_setup_entrypoint_is_present(self):
        source = (bootstrap.ROOT / "setup_creator_studio.cmd").read_text(encoding="utf-8")
        self.assertIn('"%BOOTSTRAP%" --install', source)
        self.assertIn("py -3.12", source)
        self.assertIn("start_creator_studio.cmd", source)


if __name__ == "__main__":
    unittest.main()
