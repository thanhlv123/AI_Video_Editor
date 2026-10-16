import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM112Tests(unittest.TestCase):
    def _coordinator(self, use_music=True):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return AutomationPipelineCoordinator.create(
            Path(temp.name),
            script_text="hello",
            language="en",
            config={"use_music": use_music},
        )

    def test_music_selected_completes_stage_and_waits_for_timeline(self):
        c = self._coordinator()
        c.music_selection_started(candidate_count=3)
        self.assertEqual(c.state.stage_status("music"), AutomationStageStatus.RUNNING)
        c.music_selection_completed(
            status="selected",
            candidate_count=3,
            eligible_count=2,
            selected_asset_id="music_123",
            selected_duration_seconds=30,
            project_duration_seconds=60,
            loop_required=True,
        )
        self.assertEqual(c.state.stage_status("music"), AutomationStageStatus.COMPLETED)
        self.assertEqual(c.state.stage_status("timeline"), AutomationStageStatus.PENDING)
        self.assertEqual(c.status, AutomationRunStatus.WAITING)
        self.assertIn("music_selection_manifest.json", c.state.message)

    def test_no_music_skips_stage_without_failing_video(self):
        c = self._coordinator()
        c.music_selection_started(candidate_count=0)
        c.music_selection_completed(
            status="skipped_no_music",
            candidate_count=0,
            eligible_count=0,
        )
        self.assertEqual(c.state.stage_status("music"), AutomationStageStatus.SKIPPED)
        self.assertEqual(c.status, AutomationRunStatus.WAITING)
        self.assertEqual(c.state.first_incomplete_key(), "script")

    def test_disabled_music_is_skipped(self):
        c = self._coordinator(use_music=False)
        c.music_selection_started(candidate_count=0)
        c.music_selection_completed(
            status="skipped_disabled",
            candidate_count=0,
            eligible_count=0,
        )
        self.assertEqual(c.state.stage_status("music"), AutomationStageStatus.SKIPPED)


if __name__ == "__main__":
    unittest.main()
