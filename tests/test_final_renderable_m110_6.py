import json
import tempfile
import unittest
from pathlib import Path

from creator_studio.final_renderable import (
    FINAL_RENDERABLE_FILENAME,
    FinalRenderableAssetService,
)
from creator_studio.project_storage import (
    finalize_media_asset,
    initialize_project_layout,
    new_media_asset_target,
)
from creator_studio.scene_assets import assign_media_asset


class FinalRenderableM1106Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        initialize_project_layout(self.root)
        self.run_dir = self.root / "work" / "automation" / "run_test"
        self.run_dir.mkdir(parents=True)
        self.scenes_path = self.root / "work" / "voice" / "voice_test" / "run_test" / "voice_scenes.json"
        self.scenes_path.parent.mkdir(parents=True)
        self.voice_asset_id = "voice_test"

    def tearDown(self):
        self.temp.cleanup()

    def _write_scenes(self, count=2):
        scenes = []
        start = 0.0
        for index in range(1, count + 1):
            end = start + 5.0
            scenes.append({
                "id": f"scene_{index:03d}",
                "start": start,
                "end": end,
                "duration": 5.0,
                "text": f"Scene {index}",
                "scene_type": "speech",
            })
            start = end
        self.scenes_path.write_text(json.dumps(scenes), encoding="utf-8")
        return scenes

    def _asset(self, *, name="asset", duration=8.0):
        record = new_media_asset_target(
            self.root,
            media_type="video",
            origin="downloaded",
            extension=".mp4",
            display_name=name,
            provider_id="pexels",
            source_reference=f"stock:pexels:{name}",
        )
        record.media_path.write_bytes(b"fake-video-bytes")
        return finalize_media_asset(
            record,
            width=1920,
            height=1080,
            duration_seconds=duration,
        )

    def _ranking(self, scores):
        payload = {
            "format": "creator_studio_media_ranking_m110_4",
            "scene_count": len(scores),
            "scenes": [
                {
                    "scene_id": f"scene_{index:03d}",
                    "stock": {"score": score, "render_eligible": True},
                    "youtube_reference": {"render_eligible": False},
                    "ranking": {"action": "keep_stock", "render_source": "stock"},
                }
                for index, score in enumerate(scores, start=1)
            ],
        }
        path = self.run_dir / "media_ranking_manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_resolves_current_scene_assignments_to_local_render_assets(self):
        self._write_scenes(2)
        a1 = self._asset(name="one", duration=7.0)
        a2 = self._asset(name="two", duration=9.0)
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", a1.asset_id)
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_002", a2.asset_id)
        ranking = self._ranking([0.72, 0.81])

        report = FinalRenderableAssetService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            voice_asset_id=self.voice_asset_id,
            ranking_manifest_path=ranking,
        ).run()

        self.assertEqual(report.ready_count, 2)
        self.assertEqual(report.unresolved_count, 0)
        self.assertEqual(report.video_count, 2)
        payload = json.loads((self.run_dir / FINAL_RENDERABLE_FILENAME).read_text(encoding="utf-8"))
        self.assertTrue(all(item["render_eligible"] for item in payload["scenes"]))
        self.assertTrue(all(not Path(item["asset"]["path"]).is_absolute() for item in payload["scenes"]))
        self.assertEqual(payload["policy"]["youtube_render_policy"], "preview_reference_only")

    def test_missing_assignment_stays_unresolved(self):
        self._write_scenes(2)
        a1 = self._asset(name="only", duration=7.0)
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", a1.asset_id)
        ranking = self._ranking([0.72, 0.40])

        report = FinalRenderableAssetService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            voice_asset_id=self.voice_asset_id,
            ranking_manifest_path=ranking,
        ).run()

        self.assertEqual(report.ready_count, 1)
        self.assertEqual(report.unresolved_count, 1)
        payload = json.loads((self.run_dir / FINAL_RENDERABLE_FILENAME).read_text(encoding="utf-8"))
        second = payload["scenes"][1]
        self.assertFalse(second["render_eligible"])
        self.assertIn("missing_scene_assignment", second["issues"])

    def test_video_shorter_than_scene_is_not_final_renderable(self):
        self._write_scenes(1)
        asset = self._asset(name="short", duration=3.0)
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", asset.asset_id)
        ranking = self._ranking([0.95])

        report = FinalRenderableAssetService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            voice_asset_id=self.voice_asset_id,
            ranking_manifest_path=ranking,
        ).run()
        self.assertEqual(report.unresolved_count, 1)
        payload = json.loads((self.run_dir / FINAL_RENDERABLE_FILENAME).read_text(encoding="utf-8"))
        self.assertIn("video_too_short_for_scene", payload["scenes"][0]["issues"])

    def test_research_decision_drives_final_quality_metadata_not_render_authority(self):
        self._write_scenes(1)
        asset = self._asset(name="improved", duration=8.0)
        assign_media_asset(self.root, self.voice_asset_id, self.scenes_path, "scene_001", asset.asset_id)
        ranking = self._ranking([0.31])
        research = self.run_dir / "media_research_manifest.json"
        research.write_text(json.dumps({
            "format": "creator_studio_media_research_m110_5",
            "scenes": [{
                "scene_id": "scene_001",
                "original": {"score": 0.31},
                "research": {"score": 0.82},
                "decision": {"accepted_new_asset": True, "outcome": "improved", "render_source": "stock"},
            }],
        }), encoding="utf-8")

        FinalRenderableAssetService(
            project_root=self.root,
            run_dir=self.run_dir,
            source_scenes_path=self.scenes_path,
            voice_asset_id=self.voice_asset_id,
            ranking_manifest_path=ranking,
            research_manifest_path=research,
        ).run()
        payload = json.loads((self.run_dir / FINAL_RENDERABLE_FILENAME).read_text(encoding="utf-8"))
        scene = payload["scenes"][0]
        self.assertEqual(scene["selection"]["source"], "m110_5_research")
        self.assertAlmostEqual(scene["selection"]["score"], 0.82)
        self.assertTrue(scene["render_eligible"])
        self.assertEqual(scene["asset"]["provider_id"], "pexels")


if __name__ == "__main__":
    unittest.main()
