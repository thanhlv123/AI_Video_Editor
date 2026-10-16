import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM113Tests(unittest.TestCase):
    def _coordinator(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return AutomationPipelineCoordinator.create(
            Path(temp.name), script_text="hello", language="en", config={"use_music": True}
        )

    def test_timeline_ready_completes_stage_and_waits_for_render(self):
        c = self._coordinator()
        c.timeline_assembly_started(total_scene_count=2)
        self.assertEqual(c.state.stage_status("timeline"), AutomationStageStatus.RUNNING)
        c.timeline_assembly_completed(
            status="ready", scene_count=2, visual_clip_count=2, gap_fill_count=0,
            duration_seconds=9.0, music_included=True,
        )
        self.assertEqual(c.state.stage_status("timeline"), AutomationStageStatus.COMPLETED)
        self.assertEqual(c.state.stage_status("render"), AutomationStageStatus.PENDING)
        self.assertEqual(c.status, AutomationRunStatus.WAITING)
        self.assertIn("M114", c.state.message)

    def test_timeline_progress_is_persisted(self):
        c = self._coordinator()
        c.timeline_assembly_started(total_scene_count=4)
        c.timeline_assembly_progress(current=2, total=4, scene_id="scene_002", status="scene_bound")
        self.assertEqual(c.state.stage_status("timeline"), AutomationStageStatus.RUNNING)
        self.assertIn("scene_002", c.state.message)

    def test_invalid_timeline_status_fails_stage(self):
        c = self._coordinator()
        c.timeline_assembly_completed(
            status="unresolved", scene_count=1, visual_clip_count=0, gap_fill_count=0,
            duration_seconds=1.0, music_included=False,
        )
        self.assertEqual(c.state.stage_status("timeline"), AutomationStageStatus.FAILED)
        self.assertEqual(c.status, AutomationRunStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
