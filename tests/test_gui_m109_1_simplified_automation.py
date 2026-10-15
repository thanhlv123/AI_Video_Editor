import ast
import unittest
from pathlib import Path


class M1091SimplifiedAutomationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_path = Path(__file__).resolve().parents[1] / "gui_creator_studio_m109_1.py"
        cls.text = cls.gui_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text, filename=str(cls.gui_path))
        cls.classes = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef)
        }

    def test_automation_page_and_progress_surface_exist(self):
        self.assertIn("AutomationPage", self.classes)
        for token in (
            'QLabel("Tạo video tự động")',
            'QPushButton("TẠO VIDEO")',
            'QLabel("Tiến trình tạo video")',
            'QLabel("Tổng tiến trình")',
            "QProgressBar()",
        ):
            self.assertIn(token, self.text)

    def test_main_navigation_is_simplified_and_advanced_is_collapsible(self):
        self.assertIn('NavItem("automation", "Tạo video", "▶")', self.text)
        self.assertIn('NavItem("project", "Dự án", "P")', self.text)
        self.assertIn('NavItem("settings", "Cài đặt", "ST")', self.text)
        self.assertIn('QPushButton("  ▸ Nâng cao")', self.text)
        self.assertIn("button.setVisible(False)", self.text)
        self.assertIn("def _toggle_advanced_navigation", self.text)

    def test_manual_m108_surfaces_are_preserved_under_advanced(self):
        for key in ("voice", "scenes", "media", "vision", "timeline", "export", "diagnostics"):
            self.assertIn(f'NavItem("{key}"', self.text)
        for token in (
            "VoiceScriptPage(",
            "SceneAssetAssignmentPage(",
            "MediaAssetLibraryPage(",
            '"timeline",',
            '"export",',
        ):
            self.assertIn(token, self.text)

    def test_stage_labels_cover_current_user_facing_pipeline(self):
        workflow_path = self.gui_path.parent / "creator_studio" / "automation_workflow.py"
        workflow_text = workflow_path.read_text(encoding="utf-8")
        for label in (
            "Kịch bản",
            "Tạo giọng đọc",
            "Phân tích nội dung",
            "Chia cảnh",
            "Tìm ảnh & video",
            "Chuẩn bị tư liệu",
            "Thêm nhạc nền",
            "Dựng video",
            "Xuất video",
            "Hoàn tất",
        ):
            self.assertIn(label, workflow_text)

    def test_setup_keeps_only_high_value_user_controls(self):
        for token in (
            'self.preset_combo = QComboBox()',
            'self.mode_combo = QComboBox()',
            'self.aspect_combo = QComboBox()',
            'self.quality_combo = QComboBox()',
            'QPushButton("Thiết lập giọng đọc")',
            'QPushButton("▸ Tùy chọn nâng cao")',
        ):
            self.assertIn(token, self.text)

    def test_default_page_is_automation(self):
        self.assertIn('self.navigate_to("automation")', self.text)
        self.assertIn('self._register_page("automation", self.automation_page)', self.text)

    def test_project_script_is_saved_before_workflow_preview(self):
        self.assertIn("def _prepare_automation_workflow", self.text)
        self.assertIn("self._persist_script_file(script_text)", self.text)
        self.assertIn("self._ingest_script_text(", self.text)
        self.assertIn("self._automation_workflow_from_project()", self.text)

    def test_m109_1_does_not_claim_runner_is_connected(self):
        self.assertIn("Automation Runner thực thi liên hoàn sẽ được nối ở M109.2", self.text)
        self.assertIn("self.pause_button.setEnabled(False)", self.text)
        self.assertIn("self.cancel_button.setEnabled(False)", self.text)

    def test_footer_is_m109_1(self):
        self.assertIn("Creator Studio · M109.1 Simplified Automation UI", self.text)


if __name__ == "__main__":
    unittest.main()
