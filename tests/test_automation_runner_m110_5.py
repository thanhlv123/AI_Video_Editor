from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM1105Tests(unittest.TestCase):
    def test_research_completion_advances_when_render_safe_fallbacks_cover_all_scenes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            c = AutomationPipelineCoordinator.create(root, script_text="hello", language="en")
            c.media_research_started(target_count=1)
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)
            c.media_research_completed(
                total_scene_count=4,
                target_count=1,
                improved_count=0,
                acquired_count=0,
                fallback_preserved_count=1,
                unresolved_count=0,
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.COMPLETED)
            self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.COMPLETED)
            self.assertIn("nhạc nền", c.state.message)

    def test_research_waits_for_m1106_when_render_asset_is_still_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            c = AutomationPipelineCoordinator.create(root, script_text="hello", language="en")
            c.media_research_completed(
                total_scene_count=4,
                target_count=2,
                improved_count=1,
                acquired_count=0,
                fallback_preserved_count=0,
                unresolved_count=1,
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.RUNNING)
            self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.PENDING)
            self.assertIn("M110.6", c.state.message)


if __name__ == "__main__":
    unittest.main()
