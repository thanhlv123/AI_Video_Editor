import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

GUI_M113 = ROOT / "gui_creator_studio_m113.py"
GUI_M114 = ROOT / "gui_creator_studio_m114.py"


class GuiM114RenderExportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = GUI_M114.read_text(
            encoding="utf-8"
        )

    def test_footer_identifies_m114(self):
        self.assertIn(
            (
                "Creator Studio · "
                "M114 Render Runtime Export"
            ),
            self.source,
        )

    def test_gui_declares_render_export_worker(self):
        self.assertIn(
            "class RenderExportWorker(QThread):",
            self.source,
        )

        self.assertIn(
            "self.render_export_worker",
            self.source,
        )

        self.assertIn(
            "RenderCancellationToken",
            self.source,
        )

        self.assertIn(
            "RenderBackendCancelled",
            self.source,
        )

    def test_worker_calls_automation_coordinator(self):
        self.assertIn(
            "self.coordinator.run_render_export(",
            self.source,
        )

        self.assertIn(
            "timeline_manifest_path=(",
            self.source,
        )

        self.assertIn(
            "cancel_token=self.cancel_token",
            self.source,
        )

    def test_gui_does_not_call_ffmpeg_directly(self):
        self.assertNotIn(
            "subprocess.Popen(",
            self.source,
        )

        self.assertNotIn(
            "subprocess.run(",
            self.source,
        )

        self.assertNotIn(
            "ffmpeg -",
            self.source.lower(),
        )

    def test_timeline_success_chains_into_render_export(self):
        self.assertIn(
            "_on_timeline_assembly_succeeded",
            self.source,
        )

        self.assertIn(
            "_automation_start_render_export",
            self.source,
        )

        self.assertIn(
            (
                "self."
                "_automation_start_render_export(path)"
            ),
            self.source,
        )

    def test_render_signals_are_wired(self):
        self.assertIn(
            (
                "worker.progress.connect("
                "\n"
                "            "
                "self._on_render_export_progress"
            ),
            self.source,
        )

        self.assertIn(
            (
                "worker.succeeded.connect("
                "\n"
                "            "
                "self._on_render_export_succeeded"
            ),
            self.source,
        )

        self.assertIn(
            (
                "worker.failed.connect("
                "\n"
                "            "
                "self._on_render_export_failed"
            ),
            self.source,
        )

        self.assertIn(
            (
                "worker.cancelled.connect("
                "\n"
                "            "
                "self._on_render_export_cancelled"
            ),
            self.source,
        )

    def test_render_progress_refreshes_automation_state(self):
        self.assertIn(
            (
                "def _on_render_export_progress("
            ),
            self.source,
        )

        self.assertIn(
            "self._automation_apply_state()",
            self.source,
        )

    def test_cancel_reaches_render_cancellation_token(self):
        self.assertIn(
            "def request_cancel(self):",
            self.source,
        )

        self.assertIn(
            "self.cancel_token.cancel()",
            self.source,
        )

        self.assertIn(
            (
                "self.render_export_worker."
                "request_cancel()"
            ),
            self.source,
        )

    def test_render_worker_is_cleaned_after_finish(self):
        self.assertIn(
            (
                "def "
                "_on_render_export_thread_finished"
            ),
            self.source,
        )

        self.assertIn(
            "self.render_export_worker = None",
            self.source,
        )

        self.assertIn(
            "worker.deleteLater()",
            self.source,
        )

    def test_m113_checkpoint_is_preserved(self):
        self.assertTrue(
            GUI_M113.is_file()
        )

        m113_source = GUI_M113.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            (
                "Creator Studio · "
                "M113 Automatic Timeline Assembly"
            ),
            m113_source,
        )

        self.assertNotIn(
            "class RenderExportWorker(QThread):",
            m113_source,
        )


if __name__ == "__main__":
    unittest.main()