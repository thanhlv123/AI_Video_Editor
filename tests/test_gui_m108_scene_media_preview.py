import ast
import unittest
from pathlib import Path


class M108SceneMediaPreviewGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_path = Path(__file__).resolve().parents[1] / "gui_creator_studio_m108.py"
        cls.text = cls.gui_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text, filename=str(cls.gui_path))
        cls.scene_page = next(
            node for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "SceneAssetAssignmentPage"
        )
        cls.methods = {
            node.name: node
            for node in cls.scene_page.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_preview_controls_exist(self):
        for token in (
            'QLabel("Xem trước tư liệu")',
            'QPushButton("Xem trước")',
            'QPushButton("Tạm dừng")',
            'QPushButton("Dừng")',
            'QPushButton("Mở tư liệu")',
        ):
            self.assertIn(token, self.text)

    def test_image_preview_uses_qpixmap_without_mutating_asset(self):
        self.assertIn("QPixmap(str(path))", self.text)
        self.assertIn("KeepAspectRatio", self.text)
        method = ast.unparse(self.methods["_show_image_preview"])
        self.assertNotIn("unlink(", method)
        self.assertNotIn("write_", method)
        self.assertNotIn("copy", method)

    def test_video_preview_is_optional_qt_multimedia(self):
        self.assertIn("QT_VIDEO_PREVIEW_AVAILABLE", self.text)
        self.assertIn("QMediaPlayer", self.text)
        self.assertIn("QVideoWidget", self.text)
        self.assertIn("_play_video_preview", self.methods)
        self.assertIn("toggle_video_preview_pause", self.methods)
        self.assertIn("stop_video_preview", self.methods)

    def test_m107_assignment_contract_remains(self):
        for token in (
            "assign_media_asset(",
            "remove_scene_assignment(",
            "load_scene_assignment_state(",
            "latest_voice_scenes_path(",
        ):
            self.assertIn(token, self.text)

    def test_footer_is_m108(self):
        self.assertIn(
            "Creator Studio · M108 Scene Workspace & Media Preview VI",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
