import ast
import unittest
from pathlib import Path


class M107GuiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / "gui_creator_studio_m107_1.py"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text, filename=str(cls.path))

    def test_scene_assignment_page_exists(self):
        names = {n.name for n in self.tree.body if isinstance(n, ast.ClassDef)}
        self.assertIn("SceneAssetAssignmentPage", names)

    def test_scene_page_is_registered_instead_of_placeholder(self):
        self.assertIn('self.scene_page = SceneAssetAssignmentPage(', self.text)
        self.assertIn('self._register_page("scenes", self.scene_page)', self.text)

    def test_manual_assignment_actions_exist(self):
        for text in (
            "Gán tư liệu cho cảnh",
            "Bỏ gán",
            "Làm mới cảnh",
            "Media Asset Library",
        ):
            self.assertIn(text, self.text)

    def test_no_scene_assignment_promotes_to_manifest_media_or_timeline(self):
        # M107 methods use the isolated scene_assets service and do not mutate
        # canonical manifest.media/timeline.
        for method_name in (
            "refresh_scene_asset_assignment",
            "assign_selected_scene_asset",
            "remove_selected_scene_asset",
        ):
            method = None
            for node in ast.walk(self.tree):
                if isinstance(node, ast.FunctionDef) and node.name == method_name:
                    method = node
                    break
            self.assertIsNotNone(method)
            source = ast.unparse(method)
            self.assertNotIn(".media =", source)
            self.assertNotIn(".timeline =", source)

    def test_footer_marks_m107_1(self):
        self.assertIn("Creator Studio · M107.1 Scene Asset Assignment VI", self.text)


if __name__ == "__main__":
    unittest.main()
