"""M117 production launcher contract tests (stdlib-only, no live providers)."""

import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from creator_studio import launcher


ROOT = Path(__file__).resolve().parents[1]


class ProductionLauncherTests(unittest.TestCase):
    def test_production_gui_is_selected_not_the_m101_shell(self):
        self.assertEqual(launcher.GUI_MODULE, "gui_creator_studio_m114")
        self.assertTrue((ROOT / launcher.GUI_FILENAME).is_file())

    def test_runtime_check_reports_missing_ffmpeg_without_running_gui(self):
        with mock.patch.object(launcher.shutil, "which", return_value=None):
            with mock.patch.object(launcher.importlib.util, "find_spec", return_value=object()):
                report = launcher.inspect_runtime()
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["ffmpeg_on_path"])
        self.assertTrue(report["checks"]["pyqt6_widgets"])

    def test_runtime_check_reports_missing_pyqt(self):
        with mock.patch.object(launcher.shutil, "which", return_value="C:/ffmpeg/bin/ffmpeg.exe"):
            with mock.patch.object(launcher.importlib.util, "find_spec", side_effect=ModuleNotFoundError):
                report = launcher.inspect_runtime()
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["pyqt6_widgets"])

    def test_check_command_emits_machine_readable_report_and_exit_code(self):
        with mock.patch.object(launcher, "inspect_runtime", return_value={"status": "blocked", "checks": {}}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = launcher.main(["--check"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")

    def test_default_command_launches_production_gui(self):
        fake_gui = SimpleNamespace(main=mock.Mock(return_value=None))
        with mock.patch.object(launcher.importlib, "import_module", return_value=fake_gui) as importer:
            code = launcher.main([])
        importer.assert_called_once_with("gui_creator_studio_m114")
        fake_gui.main.assert_called_once_with()
        self.assertEqual(code, 0)

    def test_import_failure_is_actionable_and_nonzero(self):
        output = io.StringIO()
        with mock.patch.object(launcher.importlib, "import_module", side_effect=ImportError("missing Qt")):
            with contextlib.redirect_stderr(output):
                code = launcher.main([])
        self.assertEqual(code, 1)
        self.assertIn("--check", output.getvalue())

    def test_smoke_command_reports_failure_without_traceback_or_secrets(self):
        with mock.patch.object(launcher, "inspect_runtime", return_value={"status": "ready"}):
            with mock.patch.object(launcher, "smoke_gui", side_effect=RuntimeError("window failed")):
                output = io.StringIO()
                with contextlib.redirect_stderr(output):
                    code = launcher.main(["--smoke"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")

    def test_smoke_command_uses_smoke_function(self):
        with mock.patch.object(launcher, "inspect_runtime", return_value={"status": "ready"}):
            with mock.patch.object(launcher, "smoke_gui", return_value={"status": "passed"}) as smoke:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = launcher.main(["--smoke"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "passed")
        smoke.assert_called_once_with()

    def test_legacy_gui_direct_execution_delegates_to_production_launcher(self):
        source = (ROOT / "gui_creator_studio.py").read_text(encoding="utf-8")
        self.assertIn("from creator_studio.launcher import main as _launch_main", source)
        self.assertIn("raise SystemExit(_launch_main())", source)

    def test_windows_shortcut_target_uses_stable_runner(self):
        command = (ROOT / "start_creator_studio.cmd").read_text(encoding="utf-8")
        self.assertIn("run_creator_studio.py", command)
        self.assertIn("%~dp0", command)
        self.assertIn("--check", command)


if __name__ == "__main__":
    unittest.main()
