import json
import tempfile
import unittest
from pathlib import Path

from creator_studio.visual_query_planner import (
    QUERY_PLAN_FORMAT,
    VisualQueryPlanner,
    save_query_plan,
)


class FakeSingleResult:
    def to_dict(self):
        return {
            "scene_id": "scene_001",
            "analysis": {
                "context": "night city offices",
                "subject": "office towers",
                "action": "lights remain on",
                "location": "Shanghai",
                "mood": "late night",
                "shot": "wide",
                "motion": "slow",
            },
            "search": {
                "primary_keyword": "Shanghai office towers night",
                "keywords": [
                    "Lujiazui office towers night",
                    "illuminated office windows Shanghai",
                    "Shanghai financial district night",
                ],
                "avoid": ["daytime"],
            },
            "media": {"preferred_type": "video"},
        }


class FakeSingleAnalyzer:
    def analyze(self, scene):
        self.last_scene = scene
        return FakeSingleResult()


class FakeBatchAnalyzer:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def analyze_batch(self, scenes):
        self.calls.append([scene.id for scene in scenes])
        if self.fail:
            raise RuntimeError("temporary 502")
        result = {}
        for scene in scenes:
            result[scene.id] = {
                "scene_id": scene.id,
                "context": "documentary context",
                "subject": "visible subject",
                "action": "visible action",
                "location": "Cuba",
                "mood": "documentary",
                "shot": "wide",
                "motion": "slow",
                "primary_keyword": f"Cuba {scene.id} documentary",
                "keywords": [
                    f"Cuba {scene.id} street",
                    f"Cuba {scene.id} people",
                    f"Cuba {scene.id} city",
                ],
                "avoid": ["wrong country"],
                "preferred_type": "video",
            }
        return result


def make_scenes(count):
    return [
        {
            "id": f"scene_{i:03d}",
            "start": float((i - 1) * 5),
            "end": float(i * 5),
            "duration": 5.0,
            "text": f"Cuba documentary narration scene number {i} with visible city life.",
            "scene_type": "speech",
        }
        for i in range(1, count + 1)
    ]


class VisualQueryPlannerM11012Tests(unittest.TestCase):
    def test_single_scene_compatibility_still_works(self):
        analyzer = FakeSingleAnalyzer()
        planner = VisualQueryPlanner(analyzer=analyzer, allow_dynamic_ai=False)
        plan = planner.plan_scene({
            "id": "scene_001",
            "start": 0.0,
            "end": 5.0,
            "duration": 5.0,
            "text": "Office lights remain on late at night in Shanghai.",
            "scene_type": "speech",
        })
        self.assertEqual(plan.primary_query, "Shanghai office towers night")
        self.assertEqual(plan.planner_source, "kie_scene_ai")
        self.assertEqual(plan.preferred_type, "video")
        self.assertEqual(len(plan.dialogue_sha256), 64)

    def test_29_scenes_use_four_batch_requests_at_size_eight(self):
        analyzer = FakeBatchAnalyzer()
        planner = VisualQueryPlanner(
            batch_analyzer=analyzer,
            allow_dynamic_ai=False,
            batch_size=8,
        )
        report = planner.plan_scenes(make_scenes(29))
        self.assertEqual(len(analyzer.calls), 4)
        self.assertEqual([len(x) for x in analyzer.calls], [8, 8, 8, 5])
        self.assertEqual(report.batch_request_count, 4)
        self.assertEqual(report.ai_count, 29)
        self.assertEqual(report.fallback_count, 0)

    def test_failed_batch_falls_back_without_per_scene_ai_retry(self):
        analyzer = FakeBatchAnalyzer(fail=True)
        planner = VisualQueryPlanner(
            batch_analyzer=analyzer,
            allow_dynamic_ai=False,
            batch_size=8,
        )
        report = planner.plan_scenes(make_scenes(17))
        self.assertEqual(len(analyzer.calls), 3)
        self.assertEqual(report.batch_request_count, 3)
        self.assertEqual(report.ai_count, 0)
        self.assertEqual(report.fallback_count, 17)
        self.assertTrue(all(p.primary_query for p in report.plans))
        self.assertTrue(all(p.planner_source == "deterministic_fallback" for p in report.plans))

    def test_successful_ai_results_are_cached_across_runs(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td) / "cache"
            first_analyzer = FakeBatchAnalyzer()
            first = VisualQueryPlanner(
                batch_analyzer=first_analyzer,
                allow_dynamic_ai=False,
                batch_size=8,
                cache_dir=cache_dir,
            ).plan_scenes(make_scenes(10))
            self.assertEqual(first.ai_count, 10)
            self.assertEqual(len(first_analyzer.calls), 2)

            second_analyzer = FakeBatchAnalyzer()
            second = VisualQueryPlanner(
                batch_analyzer=second_analyzer,
                allow_dynamic_ai=False,
                batch_size=8,
                cache_dir=cache_dir,
            ).plan_scenes(make_scenes(10))
            self.assertEqual(len(second_analyzer.calls), 0)
            self.assertEqual(second.cache_hit_count, 10)
            self.assertEqual(second.batch_request_count, 0)
            self.assertTrue(all(p.planner_source == "cache_kie_batch_scene_ai" for p in second.plans))

    def test_context_change_invalidates_neighbor_cache_identity(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td) / "cache"
            VisualQueryPlanner(
                batch_analyzer=FakeBatchAnalyzer(), allow_dynamic_ai=False,
                batch_size=8, cache_dir=cache_dir,
            ).plan_scenes(make_scenes(3))

            changed = make_scenes(3)
            changed[0]["text"] = "A changed previous scene changes the context fingerprint."
            analyzer = FakeBatchAnalyzer()
            report = VisualQueryPlanner(
                batch_analyzer=analyzer, allow_dynamic_ai=False,
                batch_size=8, cache_dir=cache_dir,
            ).plan_scenes(changed)
            # Scene 1 changed, scene 2 has a changed previous-neighbor hash; scene 3 can reuse.
            self.assertEqual(report.cache_hit_count, 1)
            self.assertEqual(report.ai_count, 2)

    def test_gap_scene_uses_reuse_policy_and_no_query(self):
        planner = VisualQueryPlanner(allow_dynamic_ai=False)
        report = planner.plan_scenes([
            {"id": "gap_001", "start": 5, "end": 6, "duration": 1, "text": "", "scene_type": "gap"}
        ])
        self.assertEqual(report.plans[0].strategy, "reuse_previous")
        self.assertEqual(report.plans[0].queries, ())
        self.assertEqual(report.reused_gap_count, 1)

    def test_saved_plan_does_not_duplicate_dialogue_or_credentials(self):
        secret = "super-secret-key"
        planner = VisualQueryPlanner(
            runtime_environment={"KIE_API_KEY": secret},
            allow_dynamic_ai=False,
        )
        text = "This exact sentence should not be duplicated into the query artifact."
        report = planner.plan_scenes([
            {"id": "scene_003", "start": 0, "end": 4, "duration": 4, "text": text}
        ])
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "visual_query_plan.json"
            save_query_plan(out, report.plans, source_scenes=Path("voice_scenes.json"))
            raw = out.read_text(encoding="utf-8")
            payload = json.loads(raw)
            self.assertEqual(payload["format"], QUERY_PLAN_FORMAT)
            self.assertNotIn(text, raw)
            self.assertNotIn(secret, raw)
            self.assertEqual(payload["scene_count"], 1)


if __name__ == "__main__":
    unittest.main()
