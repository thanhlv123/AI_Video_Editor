from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from creator_studio.media_research import (
    AutomaticMediaResearchService,
    build_research_query_plan,
    should_accept_research_candidate,
)


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _query_plan(path: Path):
    _write(path, {
        "format": "creator_studio_visual_query_plan_m110_1_2",
        "plans": [
            {
                "scene_id": "scene_001", "strategy": "search",
                "start": 0, "end": 5, "duration": 5,
                "primary_query": "cuba leaving airport",
                "queries": ["cuba leaving airport", "travelers luggage cuba"],
                "subject": "Cuban travelers", "action": "leaving with luggage",
                "location": "Cuba airport", "context": "emigration departure",
                "preferred_type": "video", "avoid": [],
            },
            {
                "scene_id": "scene_002", "strategy": "search",
                "start": 5, "end": 10, "duration": 5,
                "primary_query": "Havana street",
                "queries": ["Havana street"],
                "subject": "street", "action": "walking", "location": "Havana Cuba",
                "preferred_type": "video", "avoid": [],
            },
        ],
    })


def _ranking(path: Path, *, action="broaden_stock_search", old_score=0.334):
    _write(path, {
        "format": "creator_studio_media_ranking_m110_4",
        "scenes": [
            {
                "scene_id": "scene_001",
                "stock": {"render_eligible": True, "score": old_score},
                "youtube_reference": {
                    "best_candidate": {
                        "score": 0.82,
                        "chapter_title": "Cuban airport departures",
                        "matched_query": "Cuba travelers leaving with luggage",
                        "title": "Cuba migration airport documentary",
                    }
                },
                "ranking": {
                    "action": action,
                    "semantic_preference": "youtube_reference" if action == "reference_guided_research" else "stock",
                    "requires_research": True,
                    "recommended_search_terms": ["Cuban airport departures", "travelers leaving Cuba"],
                },
            },
            {
                "scene_id": "scene_002",
                "stock": {"render_eligible": True, "score": 0.9},
                "youtube_reference": {"best_candidate": None},
                "ranking": {
                    "action": "keep_stock", "semantic_preference": "stock",
                    "requires_research": False, "recommended_search_terms": [],
                },
            },
        ],
    })


def _stock(path: Path, *, score=0.334, media_id="old1"):
    _write(path, {
        "scenes": [
            {
                "scene_id": "scene_001",
                "stock": {
                    "status": "validated",
                    "selection": {"best_score": score},
                    "selected_media": {"provider": "pixabay", "media_id": media_id, "media_type": "video", "final_score": score},
                },
            },
            {
                "scene_id": "scene_002",
                "stock": {
                    "status": "validated",
                    "selection": {"best_score": 0.9},
                    "selected_media": {"provider": "pexels", "media_id": "keep2", "media_type": "video", "final_score": 0.9},
                },
            },
        ]
    })


class MediaResearchM1105Tests(unittest.TestCase):
    def test_build_plan_targets_only_research_scene_and_broadens_queries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qp = root / "visual_query_plan.json"
            rm = root / "media_ranking_manifest.json"
            out = root / "media_research_query_plan.json"
            _query_plan(qp); _ranking(rm)
            build_research_query_plan(qp, rm, out)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["scene_count"], 1)
            plan = data["plans"][0]
            self.assertEqual(plan["scene_id"], "scene_001")
            self.assertEqual(plan["planner_source"], "m110_5_targeted_research")
            self.assertIn("documentary footage", " ".join(plan["queries"]).lower())

    def test_reference_guided_plan_prefers_reference_terms(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qp = root / "visual_query_plan.json"
            rm = root / "media_ranking_manifest.json"
            out = root / "media_research_query_plan.json"
            _query_plan(qp); _ranking(rm, action="reference_guided_research")
            build_research_query_plan(qp, rm, out)
            data = json.loads(out.read_text(encoding="utf-8"))
            plan = data["plans"][0]
            self.assertEqual(plan["primary_query"], "Cuban airport departures")
            self.assertEqual(plan["research_source"], "youtube_reference")

    def test_replacement_gate_is_conservative(self):
        self.assertTrue(should_accept_research_candidate(old_validated=True, old_score=0.334, new_validated=True, new_score=0.72))
        self.assertFalse(should_accept_research_candidate(old_validated=True, old_score=0.80, new_validated=True, new_score=0.82))
        self.assertTrue(should_accept_research_candidate(old_validated=True, old_score=0.82, new_validated=True, new_score=0.86))
        self.assertTrue(should_accept_research_candidate(old_validated=False, old_score=None, new_validated=True, new_score=0.30))
        self.assertFalse(should_accept_research_candidate(old_validated=False, old_score=None, new_validated=False, new_score=None))

    def test_service_assigns_only_clear_improvement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = root / "work" / "automation" / "run_test"
            run.mkdir(parents=True)
            qp = run / "visual_query_plan.json"
            rm = run / "media_ranking_manifest.json"
            sm = run / "stock_acquisition_manifest.json"
            vs = root / "voice_scenes.json"
            _query_plan(qp); _ranking(rm); _stock(sm); _write(vs, [])
            seen = {"assign_assets": None, "assigned": []}

            def factory(**kwargs):
                seen["assign_assets"] = kwargs.get("assign_assets")
                class FakeService:
                    def run(self_nonlocal):
                        out = Path(kwargs["run_dir"]) / "stock_acquisition_manifest.json"
                        _write(out, {"scenes": [{
                            "scene_id": "scene_001",
                            "stock": {
                                "status": "validated",
                                "selection": {"best_score": 0.78},
                                "selected_media": {"provider": "pexels", "media_id": "new1", "media_type": "video", "final_score": 0.78},
                            },
                        }]})
                        return SimpleNamespace(manifest_path=str(out))
                return FakeService()

            record = SimpleNamespace(asset_id="asset_new1")
            service = AutomaticMediaResearchService(
                project_root=root,
                run_dir=run,
                query_plan_path=qp,
                source_scenes_path=vs,
                voice_asset_id="voice_1",
                ranking_manifest_path=rm,
                stock_manifest_path=sm,
                runtime_environment={"PEXELS_API_KEY": "x"},
                stock_service_factory=factory,
                asset_lookup=lambda identity, duration: record if identity["media_id"] == "new1" else None,
                asset_assigner=lambda scene_id, rec: seen["assigned"].append((scene_id, rec.asset_id)),
            )
            report = service.run()
            self.assertFalse(seen["assign_assets"])
            self.assertEqual(seen["assigned"], [("scene_001", "asset_new1")])
            self.assertEqual(report.improved_count, 1)
            self.assertEqual(report.fallback_preserved_count, 0)
            self.assertEqual(report.unresolved_count, 0)

    def test_service_preserves_existing_fallback_when_new_stock_is_not_better(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = root / "work" / "automation" / "run_test"
            run.mkdir(parents=True)
            qp = run / "visual_query_plan.json"
            rm = run / "media_ranking_manifest.json"
            sm = run / "stock_acquisition_manifest.json"
            vs = root / "voice_scenes.json"
            _query_plan(qp); _ranking(rm, old_score=0.80); _stock(sm, score=0.80); _write(vs, [])
            assigned = []

            def factory(**kwargs):
                class FakeService:
                    def run(self_nonlocal):
                        out = Path(kwargs["run_dir"]) / "stock_acquisition_manifest.json"
                        _write(out, {"scenes": [{
                            "scene_id": "scene_001",
                            "stock": {
                                "status": "validated",
                                "selection": {"best_score": 0.82},
                                "selected_media": {"provider": "pexels", "media_id": "new1", "media_type": "video", "final_score": 0.82},
                            },
                        }]})
                        return SimpleNamespace(manifest_path=str(out))
                return FakeService()

            service = AutomaticMediaResearchService(
                project_root=root,
                run_dir=run,
                query_plan_path=qp,
                source_scenes_path=vs,
                voice_asset_id="voice_1",
                ranking_manifest_path=rm,
                stock_manifest_path=sm,
                stock_service_factory=factory,
                asset_lookup=lambda identity, duration: SimpleNamespace(asset_id="should_not_assign"),
                asset_assigner=lambda scene_id, rec: assigned.append(scene_id),
            )
            report = service.run()
            self.assertEqual(assigned, [])
            self.assertEqual(report.improved_count, 0)
            self.assertEqual(report.fallback_preserved_count, 1)
            self.assertEqual(report.unresolved_count, 0)
            data = json.loads(Path(report.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(data["scenes"][0]["decision"]["outcome"], "fallback_preserved")


if __name__ == "__main__":
    unittest.main()
