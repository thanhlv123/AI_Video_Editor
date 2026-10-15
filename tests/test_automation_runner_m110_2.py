from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM1102Tests(unittest.TestCase):
    def _coordinator(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        coordinator = AutomationPipelineCoordinator.create(
            root,
            script_text="hello world",
            language="en",
            config={},
        )
        return td, coordinator

    def test_query_plan_no_longer_waits(self):
        td, c = self._coordinator()
        try:
            c.media_query_plan_completed(scene_count=12, planned_count=12)
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.RUNNING)
        finally:
            td.cleanup()

    def test_stock_progress_advances_media_search(self):
        td, c = self._coordinator()
        try:
            c.media_stock_progress(current=5, total=10, scene_id="scene_005", phase="validated")
            stage = next(x for x in c.state.stages if x.key == "media_search")
            self.assertGreater(stage.progress, 25)
            self.assertIn("scene_005", stage.detail)
        finally:
            td.cleanup()

    def test_all_stock_resolved_completes_search_and_assignment(self):
        td, c = self._coordinator()
        try:
            c.media_stock_completed(
                total_search_scenes=10,
                validated_count=10,
                assigned_count=10,
                unresolved_count=0,
                cache_hit_count=2,
                provider_names=("pexels", "pixabay"),
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.COMPLETED)
            self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.COMPLETED)
        finally:
            td.cleanup()

    def test_unresolved_stock_waits_for_youtube_fallback(self):
        td, c = self._coordinator()
        try:
            c.media_stock_completed(
                total_search_scenes=10,
                validated_count=8,
                assigned_count=8,
                unresolved_count=2,
                provider_names=("pexels", "pixabay"),
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.RUNNING)
            self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.PENDING)
            self.assertIn("YouTube Reference", c.state.message)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
