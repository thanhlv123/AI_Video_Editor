"""Offline M65 boundary tests using real M61-M64 contracts."""
import ast
from copy import deepcopy
from dataclasses import replace, fields
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from creator_studio.manifest import ProjectManifest, validate, save, load
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.semantic import (Purpose, ReviewStatus, AnnotationOrigin,
    Mention, SourceSpan, EntityType, LocationOrigin, TemporalKind, Derivation,
    SemanticAnnotations, document_id, output_signature as semantic_output_signature,
    exact_signature)
from creator_studio.manifest.visual import *
from creator_studio.manifest.visual_validation import visual_errors, eligible_active_plan
from creator_studio.visual.models import *
from creator_studio.visual.planner import OfflineStructuralPlanner
from creator_studio.visual.engine import build_visual_plan, effective_spec, VisualError
from creator_studio.visual.stage import VisualDirectorStage
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.semantic.stage import SemanticStoryStage
from creator_studio.orchestrator import ProjectOrchestrator, ManifestRepository
from creator_studio.orchestrator.contracts import (StageContext, CancellationToken,
    Cancelled, StageStatus, ReadinessKind)
from tests.test_semantic_story import content


def active(m):
    return next(p for p in m.visual_planning.plans
                if p.visual_plan_id == m.visual_planning.active_creator_plan_id)


def install(m, p):
    m = deepcopy(m)
    m.visual_planning.plans = [p]
    m.visual_planning.active_creator_plan_id = p.visual_plan_id
    return m


def reviewed(m, level, review):
    p = active(m)
    if level == "plan":
        p = replace(p, review=review)
    elif level == "unit":
        p = replace(p, units=[replace(p.units[0], review=review), *p.units[1:]])
    else:
        u = p.units[0]
        u = replace(u, planned_shots=[replace(u.planned_shots[0], review=review),
                                     *u.planned_shots[1:]])
        p = replace(p, units=[u, *p.units[1:]])
    return install(m, replace(p, output_signature=output_signature(p)))


class FakePlanner:
    planner_id = "fake"
    planner_version = "1"

    def __init__(self, transform=lambda r: r):
        self.transform = transform

    def plan(self, d, options, control):
        return self.transform(OfflineStructuralPlanner().plan(d, options, control))


class VisualDirectorTests(unittest.TestCase):
    def setUp(self):
        self.semantic = build_semantic_story(content())
        self.built = build_visual_plan(self.semantic)
        self.p = active(self.built)
        self.d = self.semantic.semantic.documents[0]

    def test_deterministic_all_identities_and_semantic_unchanged(self):
        self.assertEqual(self.built.visual_planning, build_visual_plan(self.semantic).visual_planning)
        self.assertEqual(self.built.semantic, self.semantic.semantic)
        self.assertEqual(self.built.scenes, self.semantic.scenes)
        self.assertEqual(build_visual_plan(self.built).visual_planning, self.built.visual_planning)
        self.assertFalse(validate(self.built))
        self.assertEqual(self.p.visual_plan_id, plan_id(self.p))
        self.assertEqual(self.p.output_signature, output_signature(self.p))
        self.assertEqual(self.p.planning_signature, planning_signature(self.p.semantic_input_fingerprint, self.p.planning_spec))
        for u in self.p.units:
            self.assertEqual(u.visual_unit_id, unit_id(self.p.visual_plan_id, u))
            for s in u.planned_shots:
                self.assertEqual(s.planned_shot_id, shot_id(u.visual_unit_id, s))

    def test_baseline_unknown_and_empty_contracts(self):
        self.assertEqual(len(self.p.units), len(self.d.story_units))
        self.assertEqual(self.p.story_unit_ids, [u.story_unit_id for u in self.d.story_units])
        for u, story in zip(self.p.units, self.d.story_units):
            self.assertEqual(u.story_unit_ids, [story.story_unit_id])
            self.assertEqual(len(u.planned_shots), 1)
            self.assertEqual(u.visual_purpose, VisualPurpose.UNKNOWN)
            self.assertEqual(u.representation_mode, RepresentationMode.UNKNOWN)
            self.assertEqual(u.depiction_fidelity, DepictionFidelity.UNKNOWN)
            self.assertIsNone(u.geography_requirement)
            self.assertIsNone(u.temporal_requirement)
            self.assertEqual(u.continuity_requirements, [])
            s = u.planned_shots[0]
            for obj in (u, s):
                self.assertEqual(obj.requirements, [])
                self.assertEqual(obj.constraints, [])
                self.assertEqual(obj.review, VisualReview())
            self.assertEqual(s.shot_role, ShotRole.UNKNOWN)
            self.assertEqual(s.shot_scale_preference, ShotScale.UNKNOWN)
            self.assertEqual(s.camera_motion_preference, CameraMotion.UNKNOWN)
            self.assertEqual(s.media_form_preference, MediaFormPreference.UNKNOWN)

    def test_invalid_reference_and_structure_matrix(self):
        u = self.p.units[0]; s = u.planned_shots[0]
        cases = [replace(self.p, semantic_document_id="missing"),
                 replace(self.p, purpose=Purpose.REFERENCE_ANALYSIS),
                 replace(self.p, units=[]), replace(self.p, units=self.p.units[:1]),
                 replace(self.p, story_unit_ids=list(reversed(self.p.story_unit_ids)))]
        for change in [dict(story_unit_ids=[]), dict(story_unit_ids=["foreign"]),
                       dict(story_unit_ids=[*u.story_unit_ids, *u.story_unit_ids]),
                       dict(story_unit_ids=list(reversed(self.p.story_unit_ids))),
                       dict(planned_shots=[]), dict(ordinal=5)]:
            cases.append(replace(self.p, units=[replace(u, **change), *self.p.units[1:]]))
        for change in [dict(visual_unit_id="wrong"), dict(story_unit_ids=["foreign"]),
                       dict(story_unit_ids=self.p.units[1].story_unit_ids),
                       dict(story_unit_ids=[]), dict(ordinal=4)]:
            cases.append(replace(self.p, units=[replace(u, planned_shots=[replace(s, **change)]), *self.p.units[1:]]))
        for i, p in enumerate(cases):
            with self.subTest(case=i):
                self.assertTrue(validate(install(self.built, p)))
        m = deepcopy(self.built); m.visual_planning.active_creator_plan_id = "missing"
        self.assertTrue(validate(m))

    def test_duplicate_id_matrix(self):
        for level in ("plan", "unit", "shot"):
            m = deepcopy(self.built)
            if level == "plan":
                m.visual_planning.plans.append(self.p)
            elif level == "unit":
                m.visual_planning.plans[0] = replace(self.p, units=[*self.p.units, self.p.units[0]])
            else:
                u = self.p.units[0]
                m.visual_planning.plans[0] = replace(self.p, units=[replace(u,
                    planned_shots=[*u.planned_shots, u.planned_shots[0]]), *self.p.units[1:]])
            self.assertIn("visual_duplicate_id", visual_errors(m.visual_planning, m.semantic))

    def test_multi_unit_multi_shot_noncontiguous_contract(self):
        m = build_semantic_story(content("One.\n\nTwo.\n\nThree."))
        def grouped(r):
            ids = [u.story_unit_ids[0] for u in r.units]
            return VisualPlanningResult([
                VisualUnitCandidate([ids[0], ids[2]], planned_shots=[
                    PlannedShotCandidate([ids[0]]), PlannedShotCandidate([ids[2]]),
                    PlannedShotCandidate([ids[0], ids[2]])]),
                VisualUnitCandidate([ids[1]], planned_shots=[PlannedShotCandidate([ids[1]])]), r.units[0]])
        built = build_visual_plan(m, planner=FakePlanner(grouped))
        self.assertFalse(validate(built))
        self.assertEqual(len(active(built).units[0].planned_shots), 3)

    def test_review_types_strict(self):
        for review in [VisualReview("APPROVED", False), VisualReview(ReviewStatus.PENDING, 1),
                       VisualReview(ReviewStatus.PENDING, None)]:
            for level in ("plan", "unit", "shot"):
                with self.assertRaises(ValueError):
                    reviewed(self.built, level, review)
        for value in ("BAD", 0, None):
            bad = to_data(self.built)
            bad["visual_planning"]["plans"][0]["review"]["status"] = value
            with self.assertRaises(ValueError):
                decode(ProjectManifest, bad)

    def test_review_preservation_and_replacement_matrix(self):
        for level in ("plan", "unit", "shot"):
            for status in ReviewStatus:
                for locked in (False, True):
                    with self.subTest(level=level, status=status, locked=locked):
                        m = reviewed(self.built, level, VisualReview(status, locked))
                        before = deepcopy(m)
                        self.assertEqual(active(build_visual_plan(m)), active(m))
                        if status == ReviewStatus.APPROVED or locked:
                            with self.assertRaises(VisualError) as caught:
                                build_visual_plan(m, planner=FakePlanner())
                            self.assertEqual(caught.exception.code, "visual_review_required")
                            self.assertEqual(m, before)
                        else:
                            changed = build_visual_plan(m, planner=FakePlanner())
                            self.assertNotEqual(active(changed).visual_plan_id, self.p.visual_plan_id)
                            self.assertEqual(len(changed.visual_planning.plans), 2)

    def test_semantic_review_stales_visual_without_corrupting_history(self):
        m = reviewed(self.built, "shot", VisualReview(ReviewStatus.REJECTED, True))
        d = replace(self.d, review_status=ReviewStatus.APPROVED)
        d = replace(d, output_signature=semantic_output_signature(d))
        self.assertEqual(d.semantic_document_id, self.d.semantic_document_id)
        m.semantic.documents[0] = d
        self.assertFalse(validate(m)); self.assertIsNone(eligible_active_plan(m))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"history.json"; save(m, path)
            self.assertEqual(load(path), m)
        with self.assertRaises(VisualError) as caught:
            build_visual_plan(m)
        self.assertEqual(caught.exception.code, "visual_review_required")

    def test_content_staleness_no_automatic_history_selection(self):
        changed = build_semantic_story(content("New revision.", manifest=self.built))
        self.assertFalse(validate(changed)); self.assertIsNone(eligible_active_plan(changed))
        newer = build_visual_plan(changed); back = content(manifest=newer)
        self.assertIsNone(eligible_active_plan(back))
        self.assertEqual(back.visual_planning, newer.visual_planning)

    def test_empty_missing_reference_semantic_inputs(self):
        for m in [ProjectManifest("empty"), build_semantic_story(content("# Heading", markdown=True))]:
            with self.assertRaises(VisualError):
                build_visual_plan(m)
            self.assertEqual(VisualDirectorStage().readiness(m).kind, ReadinessKind.NOT_READY)
        m = deepcopy(self.semantic)
        m.semantic.documents[0] = replace(self.d, purpose=Purpose.REFERENCE_ANALYSIS)
        with self.assertRaises(VisualError):
            build_visual_plan(m)
        self.assertEqual(VisualDirectorStage().readiness(m).kind, ReadinessKind.NOT_READY)

    def test_invalid_candidate_exception_and_mutation_atomicity(self):
        before = deepcopy(self.semantic)
        for transform in [lambda r: None, lambda r: VisualPlanningResult([]),
                          lambda r: replace(r, units=[replace(r.units[0], story_unit_ids=["foreign"])])]:
            with self.assertRaises(VisualError):
                build_visual_plan(self.semantic, planner=FakePlanner(transform))
            self.assertEqual(self.semantic, before)
        class Explodes(FakePlanner):
            def plan(self, d, options, control):
                raise RuntimeError("PRIVATE SCRIPT C:/private/source.txt")
        with self.assertRaises(VisualError) as caught:
            build_visual_plan(self.semantic, planner=Explodes())
        self.assertEqual(caught.exception.code, "visual_planning_failed")
        self.assertNotIn("PRIVATE", str(caught.exception))
        class Mutates(FakePlanner):
            def plan(self, d, options, control):
                d.story_units.clear(); return VisualPlanningResult([])
        with self.assertRaises(VisualError):
            build_visual_plan(self.semantic, planner=Mutates())
        self.assertEqual(self.semantic, before)

    def test_cancelled_and_late_cancelled_atomicity(self):
        before = deepcopy(self.semantic)
        class Late(FakePlanner):
            def plan(self, d, options, control):
                result = super().plan(d, options, control); control.cancel(); return result
        for late in (False, True):
            token = CancellationToken()
            if not late:
                token.cancel()
            with self.assertRaises(Cancelled):
                build_visual_plan(self.semantic, planner=Late(), control=token)
            self.assertEqual(self.semantic, before)
        import creator_studio.visual.engine as engine
        token = CancellationToken(); original = engine.require_valid; calls = []
        def cancel_at_publish(m):
            original(m); calls.append(1)
            if len(calls) == 2:
                token.cancel()
        with patch.object(engine, "require_valid", cancel_at_publish):
            with self.assertRaises(Cancelled):
                build_visual_plan(self.semantic, control=token)
        self.assertEqual(self.semantic, before)

    def test_generated_output_differs_without_request_identity_change(self):
        first = build_visual_plan(self.semantic, planner=FakePlanner())
        def detail(r):
            return replace(r, units=[replace(u, visual_purpose=VisualPurpose.DETAIL) for u in r.units])
        second = build_visual_plan(self.semantic, planner=FakePlanner(detail))
        a, b = active(first), active(second)
        self.assertEqual(a.planning_signature, b.planning_signature)
        self.assertEqual(a.semantic_input_fingerprint, b.semantic_input_fingerprint)
        self.assertNotEqual(a.visual_plan_id, b.visual_plan_id)
        self.assertNotEqual(a.units[0].visual_unit_id, b.units[0].visual_unit_id)
        self.assertNotEqual(a.units[0].planned_shots[0].planned_shot_id, b.units[0].planned_shots[0].planned_shot_id)

    def test_effective_spec_strict_empty_options_and_identity_inputs(self):
        self.assertEqual(fields(PlanningOptions), ())
        for options in ({}, True, "unused option"):
            with self.assertRaises(VisualError):
                build_visual_plan(self.semantic, options=options)
        for value in ("", "bad/path", 1):
            planner = FakePlanner(); planner.planner_version = value
            with self.assertRaises(VisualError):
                build_visual_plan(self.semantic, planner=planner)
        for change in (dict(engine_version="2"), dict(planner_version="2"),
                       dict(planner_id="another"), dict(visual_contract_version="2")):
            spec = replace(self.p.planning_spec, **change)
            self.assertNotEqual(planning_signature(self.p.semantic_input_fingerprint, spec), self.p.planning_signature)
        data = to_data(self.built)
        data["visual_planning"]["plans"][0]["planning_spec"]["options"] = {"fake": True}
        with self.assertRaises(ValueError):
            decode(ProjectManifest, data)

    def test_identity_independent_of_project_clock_voice_and_scene_timing(self):
        from creator_studio.manifest.models import Scene
        m = deepcopy(self.semantic)
        m.project_id = "different-project"
        m.created_at = m.updated_at = "2000-01-01T00:00:00+00:00"
        m.voice.speed = 1.3
        m.scenes = [Scene(start=0.0, end=10.0)]
        before = deepcopy(m.scenes)
        with patch("time.time", side_effect=AssertionError("Clock forbidden")):
            built = build_visual_plan(m)
        self.assertEqual(active(built), self.p)
        self.assertEqual(built.scenes, before)

    def test_cross_document_refs_and_wrong_existing_document_rejected(self):
        m = build_semantic_story(content("Another document.", manifest=self.built))
        other = m.semantic.documents[-1]
        wrong = replace(self.p, semantic_document_id=other.semantic_document_id)
        self.assertTrue(visual_errors(install(m, wrong).visual_planning, m.semantic))
        foreign = other.story_units[0].story_unit_id
        u = replace(self.p.units[0], story_unit_ids=[foreign])
        p = assign_identity(replace(self.p, units=[u, *self.p.units[1:]]))
        self.assertIn("visual_story_unit_missing", visual_errors(install(m, p).visual_planning, m.semantic))
        self.assertIsNone(eligible_active_plan(m))

    def test_signature_diagnostic_and_requirement_tamper_matrix(self):
        for field in ("visual_plan_id", "semantic_output_signature", "content_revision_signature",
                      "semantic_input_fingerprint", "planning_signature", "output_signature"):
            with self.subTest(field=field):
                self.assertTrue(validate(install(self.built, replace(self.p, **{field: "0"*64}))))
        planner = FakePlanner(lambda r: replace(r, diagnostics=[VisualDiagnostic("PRIVATE SOURCE")]))
        with self.assertRaises(VisualError):
            build_visual_plan(self.semantic, planner=planner)
        evidence = Evidence(self.p.units[0].story_unit_ids)
        req = VisualRequirement(RequirementAspect.SUBJECT, evidence, PlanningTreatment.SHOW,
                                PlanningMetadata())
        for r in (req, replace(req, evidence=Evidence(["foreign"])),
                  replace(req, aspect=RequirementAspect.LOCATION, identity_fidelity=IdentityFidelity.EXACT)):
            planner = FakePlanner(lambda result: replace(result, units=[replace(result.units[0], requirements=[r]), *result.units[1:]]))
            with self.assertRaises(VisualError):
                build_visual_plan(self.semantic, planner=planner)

    def test_unicode_persistence_and_additive_compatibility(self):
        m = build_visual_plan(build_semantic_story(content("Tiếng Việt.\n\n日本語。\n\nمرحبا.")))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"Tiếng Việt.json"; save(m, path)
            self.assertEqual(load(path), m)
        for old in (ProjectManifest("M61"), content(), self.semantic, self.built):
            data = to_data(old); data.pop("visual_planning")
            restored = decode(ProjectManifest, migrate_document(data))
            self.assertFalse(validate(restored)); self.assertEqual(restored.visual_planning, VisualState())
        for state in (None, {}, {"plans": []}, {"plans": [], "active_creator_plan_id": None, "extra": 1}):
            data = to_data(self.semantic); data["visual_planning"] = state
            with self.assertRaises(ValueError):
                decode(ProjectManifest, migrate_document(data))

    def test_confidence_matrix(self):
        for confidence in [True, 1, -0.1, 1.1, float("nan"), float("inf")]:
            planner = FakePlanner(lambda r: replace(r, units=[replace(u,
                metadata=PlanningMetadata(AnnotationOrigin.CREATOR, confidence)) for u in r.units]))
            with self.assertRaises(VisualError):
                build_visual_plan(self.semantic, planner=planner)
        for confidence in (None, 0.0, 0.5, 1.0):
            planner = FakePlanner(lambda r: replace(r, units=[replace(u,
                metadata=PlanningMetadata(AnnotationOrigin.CREATOR, confidence)) for u in r.units]))
            self.assertFalse(validate(build_visual_plan(self.semantic, planner=planner)))

    def test_constraints_and_continuity(self):
        ids = self.p.story_unit_ids; meta = PlanningMetadata(AnnotationOrigin.CREATOR)
        def constrained(r, values):
            return replace(r, units=[replace(r.units[0], constraints=values), *r.units[1:]])
        motion = VisualConstraint(ConstraintKind.MOTION, Polarity.REQUIRE, Strength.REQUIRED, Evidence([]), meta)
        still = replace(motion, kind=ConstraintKind.STILLNESS)
        for values in [[motion, still], [motion, replace(motion, polarity=Polarity.AVOID)],
                       [replace(motion, metadata=PlanningMetadata())],
                       [replace(motion, kind=ConstraintKind.PRESERVE_LOCATION)]]:
            with self.assertRaises(VisualError):
                build_visual_plan(self.semantic, planner=FakePlanner(lambda r: constrained(r, values)))
        self.assertFalse(validate(build_visual_plan(self.semantic,
            planner=FakePlanner(lambda r: constrained(r, [motion])))))
        def inherited_conflict(r):
            u = r.units[0]
            u = replace(u, constraints=[motion], planned_shots=[replace(
                u.planned_shots[0], constraints=[still])])
            return replace(r, units=[u, *r.units[1:]])
        with self.assertRaises(VisualError):
            build_visual_plan(self.semantic, planner=FakePlanner(inherited_conflict))
        for ref in (ids, ["foreign"]):
            c = ContinuityRequirement(ContinuityKind.STYLE, Strength.PREFERRED, Evidence(ref), meta)
            planner = FakePlanner(lambda r: replace(r, units=[replace(r.units[0],
                continuity_requirements=[c]), *r.units[1:]]))
            if ref == ids:
                self.assertFalse(validate(build_visual_plan(self.semantic, planner=planner)))
            else:
                with self.assertRaises(VisualError):
                    build_visual_plan(self.semantic, planner=planner)

    def test_long_collection(self):
        m = build_semantic_story(content("\n\n".join(f"Đoạn {i}." for i in range(2000))))
        result = build_visual_plan(m)
        self.assertEqual(len(active(result).units), 2000)
        self.assertEqual(result.semantic, m.semantic); self.assertFalse(validate(result))

    def test_mention_fingerprint_ordinal_geography_temporal(self):
        m = build_semantic_story(content("Paris Paris.")); d = m.semantic.documents[0]
        u = d.story_units[0]
        mentions = [Mention(SourceSpan(0, 5), "Paris", entity_type=EntityType.PLACE,
                            location_origin=LocationOrigin.EXPLICIT),
                    Mention(SourceSpan(6, 11), "Paris", entity_type=EntityType.PLACE,
                            location_origin=LocationOrigin.EXPLICIT)]
        u = replace(u, derivation=Derivation.ANALYZER,
                    annotations=SemanticAnnotations(mentions=mentions))
        from creator_studio.manifest.semantic import story_unit_id
        u = replace(u, story_unit_id=story_unit_id(d.analysis_signature, u.source_excerpts, u.derivation))
        d = replace(d, story_units=[u]); d = replace(d, semantic_document_id=document_id(d))
        d = replace(d, output_signature=semantic_output_signature(d))
        m.semantic.documents = [d]; m.semantic.active_creator_document_id = d.semantic_document_id
        self.assertFalse(validate(m))
        refs = [SemanticMentionRef(u.story_unit_id, i, exact_signature(mention)) for i, mention in enumerate(mentions)]
        self.assertNotEqual(refs[0], refs[1])
        def requirement(r, ref):
            evidence = Evidence([u.story_unit_id], [ref])
            req = VisualRequirement(RequirementAspect.LOCATION, evidence, PlanningTreatment.SHOW,
                                    PlanningMetadata(AnnotationOrigin.CREATOR))
            return replace(r, units=[replace(r.units[0], requirements=[req],
                geography_requirement=GeographyRequirement(GeographyFidelity.EXACT, evidence))])
        for ref in refs:
            self.assertFalse(validate(build_visual_plan(m, planner=FakePlanner(lambda r: requirement(r, ref)))))
        for ref in [replace(refs[0], mention_ordinal=1), replace(refs[0], mention_ordinal=-1),
                    replace(refs[0], mention_fingerprint="bad"), replace(refs[0], story_unit_id="foreign")]:
            with self.assertRaises(VisualError):
                build_visual_plan(m, planner=FakePlanner(lambda r: requirement(r, ref)))
        for kind in ("geography", "temporal"):
            evidence = Evidence([u.story_unit_id])
            def unsupported(r):
                change = ({"geography_requirement": GeographyRequirement(GeographyFidelity.EXACT, evidence)}
                          if kind == "geography" else {"temporal_requirement": TemporalRequirement(
                              TemporalFidelity.EXACT, TemporalDimension.ERA, evidence)})
                return replace(r, units=[replace(r.units[0], **change)])
            with self.assertRaises(VisualError):
                build_visual_plan(m, planner=FakePlanner(unsupported))
        temporal_mentions = [replace(mentions[0], temporal_kind=TemporalKind.ABSOLUTE)]
        u = replace(u, annotations=SemanticAnnotations(mentions=temporal_mentions))
        d = replace(d, story_units=[u]); d = replace(d, semantic_document_id=document_id(d))
        d = replace(d, output_signature=semantic_output_signature(d))
        m.semantic.documents = [d]; m.semantic.active_creator_document_id = d.semantic_document_id
        evidence = Evidence([u.story_unit_id], [SemanticMentionRef(u.story_unit_id, 0, exact_signature(temporal_mentions[0]))])
        planner = FakePlanner(lambda r: replace(r, units=[replace(r.units[0], temporal_requirement=
            TemporalRequirement(TemporalFidelity.EXACT, TemporalDimension.ERA, evidence))]))
        self.assertFalse(validate(build_visual_plan(m, planner=planner)))

    def test_dependency_and_persisted_field_boundaries(self):
        forbidden = {"requests", "httpx", "urllib", "socket", "PyQt6", "stock",
                     "pipeline", "ffmpeg", "openai", "subprocess"}
        paths = [*Path("creator_studio/visual").glob("*.py"),
                 Path("creator_studio/manifest/visual.py"), Path("creator_studio/manifest/visual_validation.py")]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split(".")[0], forbidden)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], forbidden)
            if "manifest" in path.parts:
                self.assertNotIn("from ..visual", path.read_text())
        payload = json.dumps(to_data(self.p))
        for word in ("Pexels", "Pixabay", "retrieval_hints", "query", "asset_id", "selected_media",
                     "generation_prompt", "duration", "start_time", "end_time", "timestamp",
                     "voice", "subtitle", "timeline", "file_path", "download_url"):
            self.assertNotIn(word, payload)
        for cls in (VisualUnitCandidate, PlannedShotCandidate):
            self.assertFalse(any(f.name.endswith("_id") for f in fields(cls)))


class VisualStageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/"project.json"
        save(build_semantic_story(content()), self.path)

    def run_stage(self, stage=None):
        runner = ProjectOrchestrator(ManifestRepository(self.path))
        runner.register(stage or VisualDirectorStage()); return runner.run().results[-1]

    def test_success_artifacts_and_reuse(self):
        first = self.run_stage(); self.assertEqual(first.status, StageStatus.SUCCEEDED)
        self.assertEqual(len(first.artifacts), 3)
        m = load(self.path); p = active(m); d = m.semantic.documents[0]
        self.assertEqual(first.artifacts, VisualDirectorStage.artifacts(m, p, d))
        self.assertEqual(first.artifacts[-1].signature, exact_signature(m.semantic.source_revisions[0].content))
        self.assertEqual(self.run_stage().status, StageStatus.SKIPPED)

    def test_configurable_combined_dependencies(self):
        save(content(), self.path)
        runner = ProjectOrchestrator(ManifestRepository(self.path)); runner.register(SemanticStoryStage())
        stage = VisualDirectorStage(dependencies=("semantic_story",)); runner.register(stage)
        self.assertEqual(stage.dependencies, ("semantic_story",))
        self.assertEqual(runner.run().results[-1].status, StageStatus.SUCCEEDED)
        self.assertEqual(runner.run().results[-1].status, StageStatus.SKIPPED)

    def test_review_refresh_same_id_then_reuse(self):
        self.run_stage(); m = reviewed(load(self.path), "shot", VisualReview(ReviewStatus.APPROVED, True))
        original = active(m); save(m, self.path)
        self.assertFalse(VisualDirectorStage().validate_reuse(m, m.processing[0].execution))
        self.assertEqual(self.run_stage().status, StageStatus.SUCCEEDED)
        self.assertEqual(active(load(self.path)), original)
        self.assertEqual(self.run_stage().status, StageStatus.SKIPPED)

    def test_every_artifact_required_and_order_exact(self):
        self.run_stage(); original = load(self.path)
        for i in range(3):
            m = deepcopy(original); previous = m.processing[0].execution
            previous.artifacts.pop(i)
            self.assertFalse(VisualDirectorStage().validate_reuse(m, previous))
        m = deepcopy(original); previous = m.processing[0].execution
        previous.artifacts.reverse()
        self.assertFalse(VisualDirectorStage().validate_reuse(m, previous))

    def test_protected_stale_plan_stage_failure_preserves_domain(self):
        self.run_stage(); m = reviewed(load(self.path), "plan", VisualReview(ReviewStatus.APPROVED))
        d = replace(m.semantic.documents[0], review_status=ReviewStatus.APPROVED)
        d = replace(d, output_signature=semantic_output_signature(d))
        m.semantic.documents[0] = d; save(m, self.path)
        before = deepcopy(m)
        result = self.run_stage()
        self.assertEqual(result.status, StageStatus.FAILED)
        self.assertEqual(result.diagnostics[0].code, "visual_review_required")
        self.assertEqual(result.artifacts, [])
        after = load(self.path)
        self.assertEqual(after.visual_planning, before.visual_planning)
        self.assertEqual(after.semantic, before.semantic)

    def test_stage_cancellation_after_artifacts_has_no_update(self):
        m = load(self.path); before = deepcopy(m); token = CancellationToken()
        original = VisualDirectorStage.artifacts
        def late(*args):
            result = original(*args); token.cancel(); return result
        with patch.object(VisualDirectorStage, "artifacts", side_effect=late):
            with self.assertRaises(Cancelled):
                VisualDirectorStage().execute(StageContext(m, token, 1, lambda *_: None))
        self.assertEqual(m, before)

    def test_semantic_review_change_invalidates_reuse(self):
        self.run_stage(); m = load(self.path)
        d = replace(m.semantic.documents[0], review_status=ReviewStatus.APPROVED)
        d = replace(d, output_signature=semantic_output_signature(d))
        m.semantic.documents[0] = d; save(m, self.path)
        self.assertEqual(self.run_stage().status, StageStatus.SUCCEEDED)
        self.assertEqual(len(load(self.path).visual_planning.plans), 2)

    def test_exact_retained_formatting_and_locator_binding(self):
        for mode in ("format", "locator"):
            with self.subTest(mode=mode):
                self.run_stage(); m = load(self.path); p = active(m)
                source = m.semantic.source_revisions[0]
                record = replace(source.content, **({"original_text": source.content.original_text.replace("\n", "\r\n")}
                                  if mode == "format" else {"source_locator": "C:/different/source.txt"}))
                m.semantic.source_revisions[0] = replace(source, content=record, source_signature=exact_signature(record))
                self.assertFalse(validate(m)); save(m, self.path)
                self.assertFalse(VisualDirectorStage().validate_reuse(m, m.processing[0].execution))
                self.assertEqual(self.run_stage().status, StageStatus.SUCCEEDED)
                self.assertEqual(active(load(self.path)).visual_plan_id, p.visual_plan_id)
                self.assertEqual(self.run_stage().status, StageStatus.SKIPPED)

    def test_stage_config_version_and_missing_output_reuse_matrix(self):
        self.run_stage(); original = load(self.path)
        for mode in ("planner", "engine", "semantic_spec", "missing", "content", "artifacts", "signature", "stage_version", "status"):
            with self.subTest(mode=mode):
                m = deepcopy(original); stage = VisualDirectorStage(); previous = m.processing[0].execution
                if mode == "planner":
                    planner = OfflineStructuralPlanner(); planner.planner_version = "2"
                    stage = VisualDirectorStage(planner=planner)
                elif mode == "engine":
                    p = replace(active(m), planning_spec=replace(active(m).planning_spec, engine_version="2"))
                    p = replace(p, planning_signature=planning_signature(p.semantic_input_fingerprint, p.planning_spec))
                    p = assign_identity(p); m = install(m, p)
                elif mode == "semantic_spec":
                    stage = VisualDirectorStage(required_semantic_spec=replace(m.semantic.documents[0].analysis_spec, engine_version="2"))
                elif mode == "missing":
                    m.visual_planning = VisualState()
                elif mode == "content":
                    m = content("New revision.", manifest=m)
                elif mode == "artifacts":
                    previous.artifacts.pop()
                elif mode == "signature":
                    previous = replace(previous, dependency_signature="0"*64)
                elif mode == "stage_version":
                    previous.stage_version = "2"
                else:
                    previous.status = StageStatus.FAILED
                self.assertFalse(stage.validate_reuse(m, previous))

    def test_self_consistent_generated_forgery_rejected(self):
        self.run_stage(); m = load(self.path); p = active(m)
        p = replace(p, units=[replace(p.units[0], visual_purpose=VisualPurpose.DETAIL), *p.units[1:]])
        p = assign_identity(p); m = install(m, p); previous = m.processing[0].execution
        previous.artifacts = VisualDirectorStage.artifacts(m, p, m.semantic.documents[0])
        self.assertFalse(validate(m)); self.assertFalse(VisualDirectorStage().validate_reuse(m, previous))
        save(m, self.path); self.assertEqual(self.run_stage().status, StageStatus.SUCCEEDED)
        self.assertEqual(active(load(self.path)).units[0].visual_purpose, VisualPurpose.UNKNOWN)

    def test_future_planner_no_reuse_and_failure_no_update(self):
        self.assertEqual(self.run_stage(VisualDirectorStage(planner=FakePlanner())).status, StageStatus.SUCCEEDED)
        self.assertEqual(self.run_stage(VisualDirectorStage(planner=FakePlanner())).status, StageStatus.SUCCEEDED)
        m = reviewed(load(self.path), "unit", VisualReview(ReviewStatus.APPROVED)); before = deepcopy(m)
        result = VisualDirectorStage().execute(StageContext(m, CancellationToken(), 1, lambda *_: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertEqual(result.result.diagnostics[0].code, "visual_review_required")
        self.assertIsNone(result.update); self.assertEqual(result.result.artifacts, []); self.assertEqual(m, before)

    def test_artifacts_and_diagnostics_safe(self):
        self.run_stage(); m = load(self.path)
        payload = json.dumps(to_data(m.processing[0].execution.artifacts))
        for source in m.semantic.source_revisions:
            self.assertNotIn(source.content.normalized_text, payload)
            if source.content.source_locator:
                self.assertNotIn(source.content.source_locator, payload)
        class Bad(FakePlanner):
            def plan(self, *args):
                raise RuntimeError("PRIVATE SOURCE C:/secret.txt")
        outcome = VisualDirectorStage(planner=Bad()).execute(StageContext(m, CancellationToken(), 1, lambda *_: None))
        diagnostic = json.dumps(to_data(outcome.result.diagnostics))
        self.assertNotIn("PRIVATE", diagnostic); self.assertNotIn("secret.txt", diagnostic)
        self.assertEqual(outcome.result.artifacts, [])


if __name__ == "__main__":
    unittest.main()
