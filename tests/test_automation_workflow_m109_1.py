import unittest

from creator_studio.automation_workflow import (
    AUTOMATION_STAGES,
    AutomationStageStatus,
    AutomationWorkflowState,
)


class AutomationWorkflowM1091Tests(unittest.TestCase):
    def test_default_workflow_has_expected_order(self):
        self.assertEqual(
            [item.key for item in AUTOMATION_STAGES],
            [
                "script",
                "voice",
                "voice_timing",
                "scene_analysis",
                "media_search",
                "media_assignment",
                "music",
                "timeline",
                "render",
                "export",
            ],
        )
        state = AutomationWorkflowState()
        self.assertEqual(len(state.stages), 10)
        self.assertTrue(all(item.status == AutomationStageStatus.PENDING for item in state.stages))

    def test_completed_stages_update_progress(self):
        state = AutomationWorkflowState()
        state.mark_completed("script")
        state.mark_completed("voice")
        self.assertEqual(state.overall_progress(), 20)
        self.assertEqual(state.first_incomplete_key(), "voice_timing")

    def test_running_stage_can_report_partial_progress(self):
        state = AutomationWorkflowState()
        state.mark_completed("script")
        state.mark_running("voice", "Đang tạo voice", progress=50)
        self.assertEqual(state.stage_status("voice"), AutomationStageStatus.RUNNING)
        self.assertEqual(state.current_stage_key(), "voice")
        self.assertEqual(state.overall_progress(), 15)

    def test_only_one_stage_is_running(self):
        state = AutomationWorkflowState()
        state.mark_running("voice", progress=10)
        state.mark_running("voice_timing", progress=20)
        self.assertEqual(state.stage_status("voice"), AutomationStageStatus.PENDING)
        self.assertEqual(state.stage_status("voice_timing"), AutomationStageStatus.RUNNING)

    def test_round_trip_preserves_stage_state(self):
        state = AutomationWorkflowState(message="demo")
        state.mark_completed("script", "saved")
        state.mark_failed("voice", "provider unavailable")
        clone = AutomationWorkflowState.from_dict(state.to_dict())
        self.assertEqual(clone.message, "demo")
        self.assertEqual(clone.stage_status("script"), AutomationStageStatus.COMPLETED)
        self.assertEqual(clone.stage_status("voice"), AutomationStageStatus.FAILED)
        self.assertEqual(clone._stage("voice").detail, "provider unavailable")

    def test_unknown_stage_is_rejected(self):
        state = AutomationWorkflowState()
        with self.assertRaises(KeyError):
            state.mark_completed("not-a-stage")


if __name__ == "__main__":
    unittest.main()
