import unittest

from creator_studio.automation_workflow import (
    AUTOMATION_STAGES,
    AutomationStageStatus,
    AutomationWorkflowState,
)


class AutomationWorkflowM1092Tests(unittest.TestCase):
    def test_stage_order_is_stable(self):
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

    def test_labels_are_end_user_facing(self):
        labels = {item.key: item.label for item in AUTOMATION_STAGES}
        self.assertEqual(labels["voice_timing"], "Phân tích nội dung")
        self.assertEqual(labels["scene_analysis"], "Chia cảnh")
        self.assertEqual(labels["media_assignment"], "Chuẩn bị tư liệu")
        self.assertEqual(labels["music"], "Thêm nhạc nền")
        self.assertEqual(labels["timeline"], "Dựng video")
        self.assertEqual(labels["render"], "Xuất video")

    def test_progress_after_voice_and_scene_pipeline_is_40_percent(self):
        state = AutomationWorkflowState()
        for key in ("script", "voice", "voice_timing", "scene_analysis"):
            state.mark_completed(key)
        self.assertEqual(state.overall_progress(), 40)
        self.assertEqual(state.first_incomplete_key(), "media_search")

    def test_failed_stage_is_current_stage(self):
        state = AutomationWorkflowState()
        state.mark_completed("script")
        state.mark_failed("voice", "offline")
        self.assertEqual(state.stage_status("voice"), AutomationStageStatus.FAILED)
        self.assertEqual(state.current_stage_key(), "voice")


if __name__ == "__main__":
    unittest.main()
