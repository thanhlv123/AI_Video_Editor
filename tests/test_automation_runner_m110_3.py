from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import AutomationPipelineCoordinator, AutomationRunStatus, RUN_FORMAT
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM1103Tests(unittest.TestCase):
    def _coordinator(self):
        td = tempfile.TemporaryDirectory()
        c = AutomationPipelineCoordinator.create(
            Path(td.name), script_text='hello', language='en', config={}
        )
        return td, c

    def test_run_format_stays_backward_compatible(self):
        self.assertEqual(RUN_FORMAT, 'creator_studio_automation_run_m110_2')

    def test_stock_can_chain_to_youtube_without_breaking_m110_2_default(self):
        td, c = self._coordinator()
        try:
            c.media_stock_completed(
                total_search_scenes=3, validated_count=3, assigned_count=3,
                unresolved_count=0, continue_to_youtube=True,
            )
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)
            self.assertEqual(c.state.stage_status('media_search'), AutomationStageStatus.RUNNING)
            self.assertEqual(c.state.stage_status('media_assignment'), AutomationStageStatus.COMPLETED)
        finally:
            td.cleanup()

    def test_youtube_progress_stays_at_end_of_media_search(self):
        td, c = self._coordinator()
        try:
            c.media_youtube_progress(current=1, total=2, scene_id='scene_001', query='Havana')
            stage = next(x for x in c.state.stages if x.key == 'media_search')
            self.assertGreaterEqual(stage.progress, 96)
            self.assertLessEqual(stage.progress, 99)
            self.assertIn('YouTube Reference', stage.detail)
        finally:
            td.cleanup()

    def test_no_targets_completes_media(self):
        td, c = self._coordinator()
        try:
            c.media_stock_completed(
                total_search_scenes=3, validated_count=3, assigned_count=3,
                unresolved_count=0, continue_to_youtube=True,
            )
            c.media_youtube_completed(
                target_count=0, searched_count=0, reference_scene_count=0,
                candidate_count=0, chapter_segment_count=0,
                unresolved_stock_count=0, weak_stock_count=0,
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status('media_search'), AutomationStageStatus.COMPLETED)
            self.assertEqual(c.state.stage_status('media_assignment'), AutomationStageStatus.COMPLETED)
        finally:
            td.cleanup()

    def test_unresolved_with_references_waits_for_research(self):
        td, c = self._coordinator()
        try:
            c.media_stock_completed(
                total_search_scenes=5, validated_count=3, assigned_count=3,
                unresolved_count=2, continue_to_youtube=True,
            )
            c.media_youtube_completed(
                target_count=2, searched_count=2, reference_scene_count=2,
                candidate_count=10, chapter_segment_count=3,
                unresolved_stock_count=2, weak_stock_count=0,
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertEqual(c.state.stage_status('media_search'), AutomationStageStatus.RUNNING)
            self.assertEqual(c.state.stage_status('media_assignment'), AutomationStageStatus.PENDING)
            self.assertIn('M110.4', c.state.message)
        finally:
            td.cleanup()

    def test_missing_key_unresolved_is_waiting_not_failed(self):
        td, c = self._coordinator()
        try:
            c.media_stock_completed(
                total_search_scenes=5, validated_count=4, assigned_count=4,
                unresolved_count=1, continue_to_youtube=True,
            )
            c.media_youtube_completed(
                target_count=1, searched_count=0, reference_scene_count=0,
                candidate_count=0, chapter_segment_count=0,
                unresolved_stock_count=1, weak_stock_count=0,
                missing_api_key=True,
            )
            self.assertEqual(c.status, AutomationRunStatus.WAITING)
            self.assertNotEqual(c.status, AutomationRunStatus.FAILED)
            self.assertIn('YOUTUBE_API_KEY', c.state.message)
        finally:
            td.cleanup()


if __name__ == '__main__':
    unittest.main()
