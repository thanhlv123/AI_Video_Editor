import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM1106Tests(unittest.TestCase):
    def _coordinator(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        return AutomationPipelineCoordinator.create(
            Path(self.temp.name),
            script_text="hello",
            language="en",
            config={},
        )

    def test_final_renderable_complete_moves_media_to_music_boundary(self):
        c = self._coordinator()
        c.final_renderable_started(total_scene_count=4)
        self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.RUNNING)
        c.final_renderable_completed(
            total_scene_count=4,
            ready_count=4,
            unresolved_count=0,
            video_count=4,
            image_count=0,
        )
        self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.COMPLETED)
        self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.COMPLETED)
        self.assertEqual(c.state.stage_status("music"), AutomationStageStatus.PENDING)
        self.assertEqual(c.status, AutomationRunStatus.WAITING)
        self.assertIn("final_renderable_assets.json", c.state.message)

    def test_final_renderable_unresolved_does_not_claim_media_complete(self):
        c = self._coordinator()
        c.final_renderable_started(total_scene_count=4)
        c.final_renderable_completed(
            total_scene_count=4,
            ready_count=3,
            unresolved_count=1,
            video_count=3,
            image_count=0,
        )
        self.assertEqual(c.state.stage_status("media_assignment"), AutomationStageStatus.PENDING)
        self.assertEqual(c.state.stage_status("media_search"), AutomationStageStatus.RUNNING)
        self.assertEqual(c.status, AutomationRunStatus.WAITING)
        self.assertIn("unresolved", c.state.message)


if __name__ == "__main__":
    unittest.main()
