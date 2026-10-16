import json
import tempfile
import unittest
from pathlib import Path

from creator_studio.automation_runner import (
    AutomationPipelineCoordinator,
    AutomationRunStatus,
    RUN_FILENAME,
    RUN_FORMAT,
)
from creator_studio.automation_workflow import AutomationStageStatus


class AutomationRunnerM1092Tests(unittest.TestCase):
    """Foundational automation-runner regression tests.

    These tests intentionally run against the current shared automation runner.
    Later milestones may extend the pipeline beyond the original M109.2 stop
    point, so assertions verify durable behavior rather than an obsolete stop.
    """

    def test_create_uses_project_work_automation_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = AutomationPipelineCoordinator.create(
                root, script_text="hello", language="en", config={"preset": "Documentary"}
            )
            second = AutomationPipelineCoordinator.create(
                root, script_text="hello", language="en", config={"preset": "Documentary"}
            )
            self.assertNotEqual(first.run_dir, second.run_dir)
            self.assertTrue(first.state_path.is_file())
            self.assertTrue(second.state_path.is_file())
            self.assertEqual(
                first.run_dir.parent,
                (root / "work" / "automation").resolve(),
            )

    def test_begin_marks_script_complete_and_voice_running(self):
        with tempfile.TemporaryDirectory() as td:
            c = AutomationPipelineCoordinator.create(
                Path(td), script_text="hello", language="en", config={}
            )
            state = c.begin()
            self.assertEqual(state.stage_status("script"), AutomationStageStatus.COMPLETED)
            self.assertEqual(state.stage_status("voice"), AutomationStageStatus.RUNNING)
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)

    def test_voice_completion_moves_to_voice_timing(self):
        with tempfile.TemporaryDirectory() as td:
            c = AutomationPipelineCoordinator.create(
                Path(td), script_text="hello", language="en", config={}
            )
            c.begin()
            state = c.voice_completed(filename="voice.wav", duration_seconds=12.5)
            self.assertEqual(state.stage_status("voice"), AutomationStageStatus.COMPLETED)
            self.assertEqual(state.stage_status("voice_timing"), AutomationStageStatus.RUNNING)

    def test_voice_pipeline_completion_marks_timing_scenes_and_chains_forward(self):
        with tempfile.TemporaryDirectory() as td:
            c = AutomationPipelineCoordinator.create(
                Path(td), script_text="hello", language="en", config={}
            )
            c.begin()
            c.voice_completed(filename="voice.wav")
            state = c.voice_pipeline_completed(
                scene_count=7,
                duration_seconds=31.2,
                run_name="run_demo",
            )
            self.assertEqual(
                state.stage_status("voice_timing"),
                AutomationStageStatus.COMPLETED,
            )
            self.assertEqual(
                state.stage_status("scene_analysis"),
                AutomationStageStatus.COMPLETED,
            )
            self.assertEqual(
                state.stage_status("media_search"),
                AutomationStageStatus.RUNNING,
            )
            self.assertEqual(state.first_incomplete_key(), "media_search")
            self.assertEqual(c.status, AutomationRunStatus.RUNNING)

    def test_failure_is_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            c = AutomationPipelineCoordinator.create(
                Path(td), script_text="hello", language="en", config={}
            )
            c.begin()
            c.fail("voice", "provider offline")
            payload = json.loads((c.run_dir / RUN_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], RUN_FORMAT)
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["error"], "provider offline")
            voice = next(
                x
                for x in payload["workflow"]["stages"]
                if x["key"] == "voice"
            )
            self.assertEqual(voice["status"], "failed")

    def test_cancel_is_cooperative_and_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            c = AutomationPipelineCoordinator.create(
                Path(td), script_text="hello", language="en", config={}
            )
            c.begin()
            state = c.cancel("stop after current worker")
            self.assertEqual(c.status, AutomationRunStatus.CANCELLED)
            self.assertEqual(state.stage_status("voice"), AutomationStageStatus.CANCELLED)
            payload = c.to_dict()
            self.assertEqual(payload["status"], "cancelled")

    def test_script_content_is_not_duplicated_in_run_state(self):
        with tempfile.TemporaryDirectory() as td:
            secretish = "A long script that belongs in the project manifest only."
            c = AutomationPipelineCoordinator.create(
                Path(td), script_text=secretish, language="en", config={}
            )
            raw = c.state_path.read_text(encoding="utf-8")
            self.assertNotIn(secretish, raw)
            payload = json.loads(raw)
            self.assertEqual(len(payload["script_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
