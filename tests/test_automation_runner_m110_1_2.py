import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import (
    AutomationPipelineCoordinator,
    AutomationRunStatus,
    RUN_FORMAT,
)
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM11012Tests(unittest.TestCase):
    """Batch/cache regression coverage retained against the current runner."""

    def _coordinator(self, td):
        c = AutomationPipelineCoordinator.create(
            Path(td),
            script_text="hello",
            language="en",
            config={},
        )
        c.begin()
        c.voice_completed(filename="voice.wav", duration_seconds=10)
        return c

    def test_voice_pipeline_chains_into_media_search_stage(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._coordinator(td)
            state = c.voice_pipeline_completed(
                scene_count=5,
                duration_seconds=20,
                run_name="run_voice",
            )
            self.assertEqual(
                state.stage_status("scene_analysis"),
                AutomationStageStatus.COMPLETED,
            )
            self.assertEqual(
                state.stage_status("media_search"),
                AutomationStageStatus.RUNNING,
            )
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)

    def test_batch_activity_stays_inside_first_quarter(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._coordinator(td)
            c.voice_pipeline_completed(scene_count=29)
            state = c.media_query_activity(
                "Đang phân tích nhóm cảnh 2/4 · 8 cảnh...",
                progress=7,
            )
            stage = next(x for x in state.stages if x.key == "media_search")
            self.assertEqual(stage.progress, 7)
            self.assertIn("2/4", stage.detail)
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)

    def test_query_progress_uses_first_quarter_of_media_search(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._coordinator(td)
            c.voice_pipeline_completed(scene_count=4)
            state = c.media_query_progress(
                current=2,
                total=4,
                scene_id="scene_002",
                primary_query="old theater",
            )
            stage = next(x for x in state.stages if x.key == "media_search")
            self.assertGreater(stage.progress, 1)
            self.assertLessEqual(stage.progress, 25)
            self.assertIn("scene_002", stage.detail)

    def test_query_plan_completion_reports_batch_cache_and_fallback_stats(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._coordinator(td)
            c.voice_pipeline_completed(scene_count=29)
            state = c.media_query_plan_completed(
                scene_count=29,
                planned_count=29,
                ai_count=20,
                cache_hit_count=7,
                fallback_count=2,
                batch_request_count=3,
            )
            stage = next(x for x in state.stages if x.key == "media_search")
            self.assertEqual(stage.status, AutomationStageStatus.RUNNING)
            self.assertEqual(stage.progress, 25)
            self.assertIn("AI 20", stage.detail)
            self.assertIn("cache 7", stage.detail)
            self.assertIn("fallback 2", stage.detail)
            self.assertIn("3 batch KIE", stage.detail)
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)

    def test_current_run_format_is_m110_2(self):
        self.assertEqual(RUN_FORMAT, "creator_studio_automation_run_m110_2")

    def test_state_has_no_api_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            c = AutomationPipelineCoordinator.create(
                Path(td),
                script_text="hello",
                language="en",
                config={"preset": "Documentary"},
            )
            raw = c.state_path.read_text(encoding="utf-8")
            self.assertNotIn("KIE_API_KEY", raw)


if __name__ == "__main__":
    unittest.main()
