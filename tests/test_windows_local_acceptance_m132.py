"""M132 Windows-local acceptance regression tests."""
from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import m132_windows_local_acceptance as acceptance


READY_BOOTSTRAP = {"status": "ready", "checks": {"local_environment": True}}
BLOCKED_BOOTSTRAP = {"status": "blocked", "checks": {"local_environment": False}}
READY_STARTUP = {"status": "ready", "checks": {}}
READY_DOCTOR = {"status": "ready", "required_failures": []}
PASSED_SMOKE = {"status": "passed", "window_created": True}


class WindowsLocalAcceptanceTests(unittest.TestCase):
    def test_local_ready_requires_bootstrap_runtime_doctor_and_gui_smoke(self):
        with patch.object(
            acceptance.m131_bootstrap, "inspect_environment", return_value=READY_BOOTSTRAP
        ), patch.object(
            acceptance.launcher, "inspect_runtime", return_value=READY_STARTUP
        ), patch.object(
            acceptance.runtime_doctor, "diagnose", return_value=READY_DOCTOR
        ), patch.object(
            acceptance.launcher, "smoke_gui", return_value=PASSED_SMOKE
        ):
            report = acceptance.run_acceptance()

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["mode"], "local")
        self.assertEqual(report["gui_smoke"]["status"], "passed")

    def test_local_blocked_when_repository_environment_is_not_ready(self):
        with patch.object(
            acceptance.m131_bootstrap, "inspect_environment", return_value=BLOCKED_BOOTSTRAP
        ), patch.object(
            acceptance.launcher, "inspect_runtime", return_value=READY_STARTUP
        ), patch.object(
            acceptance.runtime_doctor, "diagnose", return_value=READY_DOCTOR
        ), patch.object(
            acceptance.launcher, "smoke_gui"
        ) as smoke:
            report = acceptance.run_acceptance()

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["gui_smoke"]["status"], "skipped")
        smoke.assert_not_called()

    def test_ci_mode_does_not_require_repository_local_venv(self):
        with patch.object(
            acceptance.m131_bootstrap, "inspect_environment", return_value=BLOCKED_BOOTSTRAP
        ), patch.object(
            acceptance.launcher, "inspect_runtime", return_value=READY_STARTUP
        ), patch.object(
            acceptance.runtime_doctor, "diagnose", return_value=READY_DOCTOR
        ), patch.object(
            acceptance.launcher, "smoke_gui", return_value=PASSED_SMOKE
        ):
            report = acceptance.run_acceptance(ci_mode=True)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["mode"], "ci")

    def test_gui_smoke_failure_blocks_acceptance(self):
        with patch.object(
            acceptance.m131_bootstrap, "inspect_environment", return_value=READY_BOOTSTRAP
        ), patch.object(
            acceptance.launcher, "inspect_runtime", return_value=READY_STARTUP
        ), patch.object(
            acceptance.runtime_doctor, "diagnose", return_value=READY_DOCTOR
        ), patch.object(
            acceptance.launcher, "smoke_gui", side_effect=RuntimeError("synthetic")
        ):
            report = acceptance.run_acceptance()

        self.assertEqual(report["status"], "blocked")
        self.assertIn("RuntimeError", report["gui_smoke"]["error"])

    def test_main_writes_machine_readable_report(self):
        with TemporaryDirectory() as directory:
            report_path = Path(directory) / "acceptance.json"
            with patch.object(
                acceptance, "run_acceptance",
                return_value={"format": "x", "mode": "ci", "status": "ready"},
            ):
                with patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(
                        acceptance.main(["--ci", "--report", str(report_path)]),
                        0,
                    )
            self.assertEqual(json.loads(output.getvalue())["status"], "ready")
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["status"], "ready")

    def test_windows_verification_entrypoint_is_present(self):
        source = (acceptance.ROOT / "verify_creator_studio.cmd").read_text(encoding="utf-8")
        self.assertIn(".venv\\Scripts\\python.exe", source)
        self.assertIn("m132_windows_local_acceptance.py", source)
        self.assertIn("setup_creator_studio.cmd", source)


if __name__ == "__main__":
    unittest.main()
