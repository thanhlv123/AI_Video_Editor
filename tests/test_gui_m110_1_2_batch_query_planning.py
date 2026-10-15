import ast
import unittest
from pathlib import Path


class M11012GuiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_path = Path(__file__).resolve().parents[1] / "gui_creator_studio_m110_1_2.py"
        cls.text = cls.gui_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text, filename=str(cls.gui_path))

    def test_query_worker_uses_batch_planner(self):
        self.assertIn("class SceneQueryPlanningWorker", self.text)
        self.assertIn("planner.plan_scenes", self.text)
        self.assertIn("batch_size=8", self.text)
        self.assertIn("cache_dir=cache_dir", self.text)

    def test_cache_is_project_local(self):
        self.assertIn('coordinator.project_root / "cache" / "scene_intelligence"', self.text)

    def test_batch_activity_updates_same_automation_screen(self):
        self.assertIn("activity = pyqtSignal(str, int)", self.text)
        self.assertIn("def _on_media_query_activity", self.text)
        self.assertIn("coordinator.media_query_activity", self.text)
        self.assertIn("self._automation_apply_state()", self.text)

    def test_voice_pipeline_auto_chains_to_query_planning(self):
        self.assertIn("self.automation_coordinator.voice_pipeline_completed", self.text)
        self.assertIn("_automation_start_media_query_planning", self.text)
        self.assertIn("QTimer.singleShot", self.text)

    def test_media_query_worker_is_initialized_before_first_start_request(self):
        window_class = next(
            node for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CreatorStudioWindow"
        )
        init_method = next(
            node for node in window_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        initialized = set()
        for node in ast.walk(init_method):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        initialized.add(target.attr)
        self.assertIn("media_query_worker", initialized)

    def test_m110_1_2_footer(self):
        self.assertIn("Creator Studio · M110.1.2 Batch Scene Intelligence + Cache", self.text)


if __name__ == "__main__":
    unittest.main()
