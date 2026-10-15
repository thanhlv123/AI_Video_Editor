import json
import os
import tempfile
import unittest
from pathlib import Path

from creator_studio.visual_query_planner import (
    QUERY_PLAN_FORMAT,
    VisualQueryPlanner,
    save_query_plan,
)


class FakeResult:
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


class FakeAnalyzer:
    def analyze(self, scene):
        self.last_scene = scene
        return FakeResult()


class VisualQueryPlannerM1101Tests(unittest.TestCase):
    def test_ai_analysis_becomes_compact_search_plan(self):
        analyzer = FakeAnalyzer()
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
        self.assertIn("Lujiazui office towers night", plan.queries)
        self.assertEqual(len(plan.dialogue_sha256), 64)

    def test_gap_scene_uses_reuse_policy_and_no_query(self):
        planner = VisualQueryPlanner(allow_dynamic_ai=False)
        plan = planner.plan_scene({
            "id": "gap_001", "start": 5.0, "end": 6.0, "duration": 1.0,
            "text": "", "scene_type": "gap",
        })
        self.assertEqual(plan.strategy, "reuse_previous")
        self.assertEqual(plan.queries, ())

    def test_fallback_is_deterministic_and_not_empty(self):
        planner = VisualQueryPlanner(language="en", allow_dynamic_ai=False)
        scene = {
            "id": "scene_002", "start": 0, "end": 4, "duration": 4,
            "text": "The old theater closes and empty seats disappear into darkness.",
        }
        a = planner.plan_scene(scene)
        b = planner.plan_scene(scene)
        self.assertEqual(a.primary_query, b.primary_query)
        self.assertTrue(a.primary_query)
        self.assertEqual(a.planner_source, "deterministic_fallback")

    def test_saved_plan_does_not_duplicate_dialogue_text(self):
        script_fragment = "This exact sentence should not be duplicated into the query artifact."
        planner = VisualQueryPlanner(allow_dynamic_ai=False)
        plan = planner.plan_scene({
            "id": "scene_003", "start": 0, "end": 4, "duration": 4,
            "text": script_fragment,
        })
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "visual_query_plan.json"
            save_query_plan(out, [plan], source_scenes=Path("voice_scenes.json"))
            raw = out.read_text(encoding="utf-8")
            payload = json.loads(raw)
            self.assertEqual(payload["format"], QUERY_PLAN_FORMAT)
            self.assertNotIn(script_fragment, raw)
            self.assertEqual(payload["scene_count"], 1)

    def test_runtime_environment_is_not_persisted_in_plan(self):
        planner = VisualQueryPlanner(
            runtime_environment={"KIE_API_KEY": "super-secret-key"},
            allow_dynamic_ai=False,
        )
        plan = planner.plan_scene({
            "id": "scene_004", "start": 0, "end": 4, "duration": 4,
            "text": "A quiet empty theater at night.",
        })
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "plan.json"
            save_query_plan(out, [plan], source_scenes=Path("voice_scenes.json"))
            self.assertNotIn("super-secret-key", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
