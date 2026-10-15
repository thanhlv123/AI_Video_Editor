from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM11031Tests(unittest.TestCase):
    def _coordinator(self):
        td = tempfile.TemporaryDirectory()
        coordinator = AutomationPipelineCoordinator.create(
            Path(td.name), script_text="hello", language="en", config={}
        )
        return td, coordinator

    def test_provider_errors_do_not_show_media_search_completed(self):
        td, coordinator = self._coordinator()
        try:
            coordinator.media_stock_completed(
                total_search_scenes=3,
                validated_count=3,
                assigned_count=3,
                unresolved_count=0,
                continue_to_youtube=True,
            )
            coordinator.media_youtube_completed(
                target_count=3,
                searched_count=0,
                reference_scene_count=0,
                candidate_count=0,
                chapter_segment_count=0,
                unresolved_stock_count=0,
                weak_stock_count=3,
                error_count=3,
            )
            self.assertEqual(coordinator.status, AutomationRunStatus.WAITING)
            self.assertEqual(
                coordinator.state.stage_status("media_search"),
                AutomationStageStatus.RUNNING,
            )
            self.assertIn("chưa hoàn tất", coordinator.state.message)
        finally:
            td.cleanup()

    def test_missing_key_with_only_weak_stock_is_not_green_completed(self):
        td, coordinator = self._coordinator()
        try:
            coordinator.media_stock_completed(
                total_search_scenes=2,
                validated_count=2,
                assigned_count=2,
                unresolved_count=0,
                continue_to_youtube=True,
            )
            coordinator.media_youtube_completed(
                target_count=1,
                searched_count=0,
                reference_scene_count=0,
                candidate_count=0,
                chapter_segment_count=0,
                unresolved_stock_count=0,
                weak_stock_count=1,
                missing_api_key=True,
            )
            self.assertEqual(coordinator.status, AutomationRunStatus.WAITING)
            self.assertEqual(
                coordinator.state.stage_status("media_search"),
                AutomationStageStatus.RUNNING,
            )
            self.assertIn("YOUTUBE_API_KEY", coordinator.state.message)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
