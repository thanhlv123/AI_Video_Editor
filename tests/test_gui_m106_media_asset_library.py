import ast
import unittest
from pathlib import Path


class M106MediaAssetLibraryGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_path = Path(__file__).resolve().parents[1] / "gui_creator_studio_m106.py"
        cls.text = cls.gui_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text, filename=str(cls.gui_path))
        cls.classes = {
            node.name: node for node in cls.tree.body if isinstance(node, ast.ClassDef)
        }
        cls.window = cls.classes["CreatorStudioWindow"]
        cls.methods = {
            node.name: node
            for node in cls.window.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_media_asset_page_exists(self):
        self.assertIn("MediaAssetLibraryPage", self.classes)

    def test_window_has_media_asset_actions(self):
        for name in (
            "refresh_media_asset_library",
            "import_image_asset",
            "import_video_asset",
            "open_selected_media_asset",
            "open_media_asset_folder",
        ):
            self.assertIn(name, self.methods)

    def test_media_page_is_registered_instead_of_placeholder(self):
        register = self.methods["_register_pages"]
        source = ast.unparse(register)
        self.assertIn("MediaAssetLibraryPage", source)
        self.assertIn("self._register_page('media', self.media_page)", source)

    def test_project_application_refreshes_media_page(self):
        source = ast.unparse(self.methods["_apply_project_to_ui"])
        self.assertIn("self.media_page.set_project", source)
        current = ast.unparse(self.methods["_set_current_project"])
        self.assertIn("self.refresh_media_asset_library()", current)

    def test_m106_does_not_assign_media_into_manifest(self):
        # M106 is storage/catalog foundation only. Scene/canonical media promotion is later.
        for name in (
            "refresh_media_asset_library",
            "_import_media_asset_dialog",
            "import_image_asset",
            "import_video_asset",
        ):
            source = ast.unparse(self.methods[name])
            self.assertNotIn("replace(self.current_project, media=", source)
            self.assertNotIn("self.current_project.media.append", source)


if __name__ == "__main__":
    unittest.main()
