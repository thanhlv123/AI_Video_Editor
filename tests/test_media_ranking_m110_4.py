from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creator_studio.media_ranking import UnifiedMediaRankingService


class MediaRankingM1104Tests(unittest.TestCase):
    def _write(self, path: Path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_unified_policy_keeps_render_safe_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stock = root / "stock_acquisition_manifest.json"
            yt = root / "youtube_reference_manifest.json"
            self._write(stock, {
                "scenes": [
                    {"scene_id": "scene_001", "stock": {"status": "validated", "selection": {"best_score": 0.92}, "selected_media": {"provider": "pexels", "media_id": "1", "media_type": "video", "final_score": 0.92}}},
                    {"scene_id": "scene_002", "stock": {"status": "validated", "selection": {"best_score": 0.55}, "selected_media": {"provider": "pixabay", "media_id": "2", "media_type": "video", "final_score": 0.55}}},
                    {"scene_id": "scene_003", "stock": {"status": "search_failed", "selected_media": None}},
                ]
            })
            self._write(yt, {
                "scenes": [
                    {"scene_id": "scene_002", "status": "searched", "candidate_count": 2, "best_candidate": {"video_id": "abc", "title": "Havana classic street cars", "channel_title": "Demo", "score": 0.88, "matched_query": "Havana classic cars", "chapter_title": "Old Havana streets", "segment_start_seconds": 20, "segment_end_seconds": 27}},
                    {"scene_id": "scene_003", "status": "searched", "candidate_count": 1, "best_candidate": {"video_id": "xyz", "title": "Cuban family home", "score": 0.80, "matched_query": "Cuba family home"}},
                ]
            })
            progress = []
            report = UnifiedMediaRankingService(
                run_dir=root,
                stock_manifest_path=stock,
                youtube_manifest_path=yt,
                progress_callback=lambda *args: progress.append(args),
            ).run()
            self.assertEqual(report.total_scene_count, 3)
            self.assertEqual(report.keep_stock_count, 1)
            self.assertEqual(report.reference_guided_count, 2)
            self.assertEqual(report.render_ready_count, 2)
            self.assertEqual(report.unresolved_render_count, 1)
            self.assertEqual(len(progress), 3)
            data = json.loads(Path(report.manifest_path).read_text(encoding="utf-8"))
            by_id = {x["scene_id"]: x for x in data["scenes"]}
            self.assertEqual(by_id["scene_001"]["ranking"]["action"], "keep_stock")
            self.assertEqual(by_id["scene_002"]["ranking"]["action"], "reference_guided_research")
            self.assertEqual(by_id["scene_002"]["ranking"]["render_source"], "stock")
            self.assertFalse(by_id["scene_002"]["youtube_reference"]["render_eligible"])
            self.assertTrue(by_id["scene_002"]["youtube_reference"]["preview_only"])
            self.assertEqual(by_id["scene_003"]["ranking"]["render_source"], "none")

    def test_low_stock_without_reference_requests_broader_stock_search(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stock = root / "stock.json"
            yt = root / "yt.json"
            self._write(stock, {"scenes": [{"scene_id": "s1", "stock": {"status": "validated", "selection": {"best_score": 0.49}, "selected_media": {"provider": "pexels", "media_id": "1", "final_score": 0.49}}}]})
            self._write(yt, {"scenes": [{"scene_id": "s1", "status": "searched", "candidate_count": 0, "best_candidate": None, "candidates": []}]})
            report = UnifiedMediaRankingService(run_dir=root, stock_manifest_path=stock, youtube_manifest_path=yt).run()
            self.assertEqual(report.broaden_search_count, 1)
            data = json.loads(Path(report.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(data["scenes"][0]["ranking"]["action"], "broaden_stock_search")
            self.assertEqual(data["scenes"][0]["ranking"]["render_source"], "stock")

    def test_output_never_promotes_youtube_to_render_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stock = root / "stock.json"
            yt = root / "yt.json"
            self._write(stock, {"scenes": [{"scene_id": "s1", "stock": {"status": "search_failed"}}]})
            self._write(yt, {"scenes": [{"scene_id": "s1", "status": "searched", "candidate_count": 1, "best_candidate": {"video_id": "v", "score": 0.99, "title": "Reference"}}]})
            report = UnifiedMediaRankingService(run_dir=root, stock_manifest_path=stock, youtube_manifest_path=yt).run()
            text = Path(report.manifest_path).read_text(encoding="utf-8")
            data = json.loads(text)
            self.assertEqual(data["policy"]["youtube_render_policy"], "preview_reference_only")
            self.assertEqual(data["scenes"][0]["ranking"]["render_source"], "none")
            self.assertNotIn("download_url", text)


if __name__ == "__main__":
    unittest.main()
