from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from creator_studio.project_storage import (
    finalize_media_asset,
    new_media_asset_target,
    scan_media_assets,
)
from creator_studio.scene_assets import load_scene_assignment_state
from creator_studio.stock_acquisition import (
    CachingDownloadAdapter,
    ProjectStockCache,
    StockAcquisitionService,
    build_stock_manifest,
    stock_source_reference,
)


class _Delegate:
    def __init__(self, folder: Path):
        self.folder = folder
        self.calls = 0

    def download(self, media, scene_id):
        self.calls += 1
        path = self.folder / f"{scene_id}_{media.get('media_id')}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-video-bytes")
        return {
            "status": "downloaded",
            "path": str(path),
            "filename": path.name,
            "size": path.stat().st_size,
        }


def _query_plan(path: Path):
    payload = {
        "format": "creator_studio_visual_query_plan_m110_1_2",
        "scene_count": 3,
        "plans": [
            {
                "scene_id": "scene_001",
                "scene_type": "speech",
                "start": 0.0,
                "end": 5.0,
                "duration": 5.0,
                "dialogue_sha256": "a",
                "primary_query": "Havana classic cars street",
                "queries": ["Havana classic cars street", "Cuba Havana vintage cars"],
                "avoid": ["Miami"],
                "preferred_type": "video",
                "planner_source": "kie_batch",
                "strategy": "search",
                "context": "Havana street life",
                "subject": "classic cars",
                "action": "driving through city streets",
                "location": "Havana Cuba",
                "mood": "documentary",
                "shot": "wide",
                "motion": "normal",
            },
            {
                "scene_id": "scene_002",
                "scene_type": "gap",
                "start": 5.0,
                "end": 6.0,
                "duration": 1.0,
                "dialogue_sha256": "b",
                "primary_query": "",
                "queries": [],
                "avoid": [],
                "preferred_type": "either",
                "planner_source": "gap_policy",
                "strategy": "reuse_previous",
            },
            {
                "scene_id": "scene_003",
                "scene_type": "speech",
                "start": 6.0,
                "end": 10.0,
                "duration": 4.0,
                "dialogue_sha256": "c",
                "primary_query": "Havana family home",
                "queries": ["Havana family home"],
                "avoid": [],
                "preferred_type": "video",
                "planner_source": "kie_batch",
                "strategy": "search",
                "context": "Cuban family",
                "subject": "family home",
                "action": "family together",
                "location": "Havana Cuba",
                "mood": "reflective",
                "shot": "medium",
                "motion": "slow",
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _voice_scenes(path: Path):
    payload = [
        {"id": "scene_001", "start": 0.0, "end": 5.0, "duration": 5.0, "text": "one", "scene_type": "speech"},
        {"id": "scene_002", "start": 5.0, "end": 6.0, "duration": 1.0, "text": "", "scene_type": "gap"},
        {"id": "scene_003", "start": 6.0, "end": 10.0, "duration": 4.0, "text": "three", "scene_type": "speech"},
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class StockAcquisitionM1102Tests(unittest.TestCase):
    def test_build_manifest_skips_gap_and_does_not_copy_narration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qp = root / "visual_query_plan.json"
            out = root / "stock.json"
            _query_plan(qp)
            build_stock_manifest(qp, out)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["scene_count"], 2)
            self.assertEqual([x["scene_id"] for x in data["scenes"]], ["scene_001", "scene_003"])
            self.assertIn("Havana classic cars", data["scenes"][0]["search"]["primary_keyword"])
            self.assertNotIn("one", data["scenes"][0]["dialogue"])

    def test_cache_reuses_asset_when_duration_is_sufficient(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record = new_media_asset_target(
                root,
                media_type="video",
                origin="downloaded",
                extension=".mp4",
                display_name="pexels_123",
                provider_id="pexels",
                source_reference=stock_source_reference("pexels", "123"),
            )
            record.media_path.write_bytes(b"video")
            finalize_media_asset(record, width=1920, height=1080, duration_seconds=8.0)
            cache = ProjectStockCache(root)
            delegate = _Delegate(root / "work")
            adapter = CachingDownloadAdapter(delegate, cache, {"scene_001": 5.0})
            result = adapter.download(
                {"provider": "pexels", "media_id": "123", "media_type": "video"},
                "scene_001",
            )
            self.assertEqual(result["status"], "cached")
            self.assertEqual(delegate.calls, 0)
            self.assertEqual(adapter.cache_hits, 1)

    def test_cache_rejects_too_short_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record = new_media_asset_target(
                root,
                media_type="video",
                origin="downloaded",
                extension=".mp4",
                display_name="pexels_123",
                provider_id="pexels",
                source_reference=stock_source_reference("pexels", "123"),
            )
            record.media_path.write_bytes(b"video")
            finalize_media_asset(record, duration_seconds=2.0)
            cache = ProjectStockCache(root)
            delegate = _Delegate(root / "work")
            adapter = CachingDownloadAdapter(delegate, cache, {"scene_001": 5.0})
            result = adapter.download(
                {"provider": "pexels", "media_id": "123", "media_type": "video"},
                "scene_001",
            )
            self.assertEqual(result["status"], "downloaded")
            self.assertEqual(delegate.calls, 1)

    def test_service_promotes_and_assigns_validated_assets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = root / "work" / "automation" / "run_test"
            run.mkdir(parents=True)
            qp = run / "visual_query_plan.json"
            scenes_path = root / "voice_scenes.json"
            _query_plan(qp)
            _voice_scenes(scenes_path)

            progress = []

            class FakeDownloader(_Delegate):
                pass

            class FakeScenePipeline:
                def __init__(self, folder):
                    self.downloader = FakeDownloader(folder)
                    self.search_manager = types.SimpleNamespace(providers=[types.SimpleNamespace(name="pexels")])

                def run(self, scene):
                    scene_id = scene["scene_id"]
                    media_id = "111" if scene_id == "scene_001" else "333"
                    selected = {"provider": "pexels", "media_id": media_id, "media_type": "video"}
                    download = self.downloader.download(selected, scene_id)
                    validation = {
                        "valid": True,
                        "duration": 10.0,
                        "width": 1920,
                        "height": 1080,
                        "fps": 30.0,
                    }
                    scene["stock"]["status"] = "validated"
                    scene["stock"]["selected_media"] = selected
                    scene["stock"]["download"] = download
                    scene["stock"]["validation"] = validation
                    return {"success": True, "status": "validated", "scene_id": scene_id}

            class FakeBatchPipeline:
                def __init__(self, manifest_path, download_dir, **kwargs):
                    self.manifest_path = Path(manifest_path)
                    self.scene_pipeline = FakeScenePipeline(Path(download_dir))

                def run(self):
                    data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                    for scene in data["scenes"]:
                        self.scene_pipeline.run(scene)
                    self.manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    return {"validated": len(data["scenes"])}

            pipeline_module = types.ModuleType("pipeline.batch_pipeline")
            pipeline_module.BatchPipeline = FakeBatchPipeline
            pipeline_pkg = sys.modules.get("pipeline") or types.ModuleType("pipeline")
            old_pipeline = sys.modules.get("pipeline")
            old_batch = sys.modules.get("pipeline.batch_pipeline")
            sys.modules["pipeline"] = pipeline_pkg
            sys.modules["pipeline.batch_pipeline"] = pipeline_module
            try:
                service = StockAcquisitionService(
                    project_root=root,
                    run_dir=run,
                    query_plan_path=qp,
                    source_scenes_path=scenes_path,
                    voice_asset_id="voice_test",
                    runtime_environment={"PEXELS_API_KEY": "test"},
                    progress_callback=lambda *args: progress.append(args),
                )
                report = service.run()
            finally:
                if old_batch is None:
                    sys.modules.pop("pipeline.batch_pipeline", None)
                else:
                    sys.modules["pipeline.batch_pipeline"] = old_batch
                if old_pipeline is None:
                    sys.modules.pop("pipeline", None)
                else:
                    sys.modules["pipeline"] = old_pipeline

            self.assertEqual(report.total_search_scenes, 2)
            self.assertEqual(report.validated_count, 2)
            self.assertEqual(report.assigned_count, 2)
            self.assertEqual(report.unresolved_count, 0)
            self.assertEqual(report.new_asset_count, 2)
            self.assertTrue(progress)
            assets = scan_media_assets(root)
            self.assertEqual(len(assets), 2)
            state = load_scene_assignment_state(root, "voice_test", scenes_path)
            self.assertEqual(len(state.assignments), 2)


if __name__ == "__main__":
    unittest.main()
