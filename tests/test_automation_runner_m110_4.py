from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM1104Tests(unittest.TestCase):
    def test_ranking_waits_for_m1105_when_research_is_needed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            c = AutomationPipelineCoordinator.create(root, script_text="hello", language="en")
            c.media_ranking_started(total_scene_count=3)
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)
            c.media_ranking_completed(
                total_scene_count=3,
                keep_stock_count=1,
                reference_guided_count=1,
                broaden_search_count=1,
                render_ready_count=2,
                unresolved_render_count=1,
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.RUNNING)
            self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.PENDING)
            self.assertIn("M110.5", c.state.message)

    def test_ranking_completes_media_when_no_research_is_needed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            c = AutomationPipelineCoordinator.create(root, script_text="hello", language="en")
            c.media_ranking_completed(
                total_scene_count=2,
                keep_stock_count=2,
                reference_guided_count=0,
                broaden_search_count=0,
                render_ready_count=2,
                unresolved_render_count=0,
            )
            self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.COMPLETED)
            self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
