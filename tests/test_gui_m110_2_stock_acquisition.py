from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_creator_studio_m110_2.py"


class GuiM1102StockAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUI.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_stock_worker_exists(self):
        classes = {node.name for node in ast.walk(self.tree) if isinstance(node, ast.ClassDef)}
        self.assertIn("StockAcquisitionWorker", classes)

    def test_window_initializes_stock_worker(self):
        self.assertIn("self.stock_acquisition_worker: StockAcquisitionWorker | None = None", self.source)

    def test_query_success_starts_stock_acquisition(self):
        self.assertIn("_automation_start_stock_acquisition", self.source)
        self.assertIn("QTimer.singleShot", self.source)

    def test_stock_success_refreshes_asset_and_assignment_views(self):
        self.assertIn("self.refresh_media_asset_library()", self.source)
        self.assertIn("self.refresh_scene_asset_assignment()", self.source)

    def test_footer_is_m110_2(self):
        self.assertIn("Creator Studio · M110.2 Automatic Stock Acquisition", self.source)


if __name__ == "__main__":
    unittest.main()
