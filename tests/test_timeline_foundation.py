"""Offline M69 contract and adversarial tests; synthetic bytes only."""
import ast
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from creator_studio.manifest import ProjectManifest, validate, save, load
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.editing import *
from creator_studio.manifest.editing_validation import editing_errors, reconstruct, project_placements
from creator_studio.manifest.acquisition import AcquisitionSpec, AcquisitionOutcome
from creator_studio.manifest.models import ProcessingState, Status
from creator_studio.manifest.signatures import dependency_signature, signature
from creator_studio.editing.engine import build_edit_plan, current_edit_eligibility, boundary_unchanged
from creator_studio.editing.stage import EditPlanningStage
from creator_studio.editing.models import EditingError
from creator_studio.acquisition.engine import build_acquisition
from creator_studio.acquisition.storage import ManagedStorage
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled, StageContext, StageStatus
from creator_studio.selection.engine import append_review
from creator_studio.manifest.selection import ReviewStatus
from tests.test_media_acquisition import OfflineProvider, OfflineInspector, CountingControl
from tests.test_media_selection import selected_fixture
from tests.test_media_retrieval import with_intent
from tests.test_semantic_story import content
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.visual.engine import build_visual_plan

class TimelineFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = selected_fixture(with_intent(build_visual_plan(build_semantic_story(content()))))

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = ManagedStorage(Path(self.temp.name) / "managed")
        self.provider, self.inspector = OfflineProvider(), OfflineInspector()
        self.acquisition_spec = AcquisitionSpec(providers=[self.provider.spec])
        self.manifest = build_acquisition(self.selected, storage=self.storage,
            providers=(self.provider,), inspector=self.inspector, spec=self.acquisition_spec)

    def build(self, manifest=None, **kwargs):
        args = dict(storage=self.storage, inspector=self.inspector, acquisition_spec=self.acquisition_spec)
        args.update(kwargs)
        return build_edit_plan(manifest if manifest is not None else self.manifest, **args)

    def stage(self, **kwargs):
        return EditPlanningStage(storage=self.storage, inspector=self.inspector,
            acquisition_spec=self.acquisition_spec, **kwargs)

    def executed(self):
        stage = self.stage()
        outcome = stage.execute(StageContext(self.manifest, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        m, execution = outcome.update.manifest, outcome.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        return stage, m, execution

    def test_empty_schema2_default(self):
        m = ProjectManifest("empty")
        self.assertEqual(m.editing, EditingState())
        self.assertEqual(m.schema_version, 2)
        self.assertFalse(validate(m))

    def test_old_schema2_and_strict_present(self):
        data = to_data(ProjectManifest("old"))
        del data["editing"]
        self.assertEqual(decode(ProjectManifest, migrate_document(data)).editing, EditingState())
        for malformed in (None, [], {}, "bad", {"plans": []}):
            with self.subTest(malformed=malformed):
                data["editing"] = malformed
                with self.assertRaises(ValueError):
                    decode(ProjectManifest, migrate_document(data))

    def test_roundtrip_and_whole_validation(self):
        m = self.build()
        target = Path(self.temp.name) / "manifest.json"
        save(m, target)
        self.assertEqual(load(target), m)
        self.assertFalse(validate(m))

    def test_exact_order_coverage_lineage_and_identity(self):
        m = self.build()
        p = m.editing.plans[0]
        visual = m.visual_planning.plans[0]
        selection = m.selection.runs[0]
        run = m.acquisition.runs[0]
        self.assertEqual([x.planned_shot_id for x in p.placements],
            [s.planned_shot_id for u in visual.units for s in u.planned_shots])
        self.assertEqual([x.shot_selection_id for x in p.placements],
            [s.shot_selection_id for s in selection.shot_selections])
        self.assertEqual([x.materialization_id for x in p.placements],
            [s.materialization_id for s in run.shot_acquisitions])
        self.assertEqual([x.ordinal for x in p.placements], list(range(len(p.placements))))
        self.assertEqual(len({x.placement_id for x in p.placements}), len(p.placements))
        self.assertEqual(p, self.build().editing.plans[0])
        self.assertEqual(p, reconstruct(m, run, EditSpec()))

    def test_non_editing_fields_unchanged(self):
        before = deepcopy(self.manifest)
        after = self.build()
        self.assertEqual(self.manifest, before)
        for f in fields(before):
            if f.name != "editing":
                with self.subTest(domain=f.name):
                    self.assertEqual(getattr(before, f.name), getattr(after, f.name))
        self.assertTrue(boundary_unchanged(before, after))

    def test_no_timing_or_render_contract(self):
        self.assertEqual(set(TimingState), {TimingState.UNRESOLVED})
        self.assertEqual({f.name for f in fields(EditPlacement)},
            {"placement_id", "ordinal", "planned_shot_id", "shot_selection_id", "acquisition_outcome", "materialization_id"})
        self.assertEqual(EditSpec(), EditSpec())
        p = self.build().editing.plans[0]
        self.assertEqual(p.timing_state, TimingState.UNRESOLVED)
        forbidden = {"start", "end", "duration", "fps", "source_start", "source_end", "source_duration",
            "timebase", "path", "url", "filename", "final_eligible", "render_ready", "rights_approved",
            "tracks", "transitions", "speed", "crop", "zoom", "resolution", "display_duration"}
        for cls in (EditSpec, EditPlacement, EditPlan, EditingState):
            self.assertFalse(forbidden & {f.name for f in fields(cls)})
        with self.assertRaises(TypeError):
            EditPlacement("x", 0, "y", "z", AcquisitionOutcome.MATERIALIZED, asset_id="bad")

    def test_inactive_or_stale_acquisition(self):
        for domain, pointer in (("acquisition", "active_creator_acquisition_id"),
                ("selection", "active_creator_selection_id"), ("retrieval", "active_creator_retrieval_id"),
                ("visual_planning", "active_creator_plan_id"), ("semantic", "active_creator_document_id")):
            m = deepcopy(self.manifest)
            setattr(getattr(m, domain), pointer, None)
            with self.subTest(domain=domain), self.assertRaises(EditingError):
                self.build(m)

    def test_wrong_acquisition_spec(self):
        with self.assertRaises(EditingError):
            self.build(acquisition_spec=AcquisitionSpec())

    def test_deleted_or_corrupt_bytes_current_not_historical(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                stage, m, execution = self.executed()
                asset = m.acquisition.assets[0]
                target = self.storage.root / asset.object_key
                original = target.read_bytes()
                if corrupt:
                    target.write_bytes(b"wrong")
                else:
                    target.unlink()
                self.assertFalse(validate(m))
                self.assertFalse(editing_errors(m))
                self.assertFalse(stage.validate_reuse(m, execution))
                with self.assertRaises(EditingError):
                    self.build(m)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)

    def test_missing_inspector(self):
        with self.assertRaises(EditingError):
            self.build(inspector=None)

    def test_readiness_no_byte_verification(self):
        with patch.object(self.storage, "verify", side_effect=AssertionError("readiness read")):
            self.assertEqual(self.stage().readiness(self.manifest).kind.value, "ready")
        prior = self.inspector.calls
        self.build()
        self.assertGreater(self.inspector.calls, prior)

    def test_no_acquisition_side_effects(self):
        with patch.object(self.provider, "resolve", side_effect=AssertionError()), \
                patch.object(self.provider, "acquire", side_effect=AssertionError()), \
                patch.object(self.storage, "staging", side_effect=AssertionError()), \
                patch.object(self.storage, "finalize", side_effect=AssertionError()):
            self.build()

    def test_projection_rejects_unequal_or_reordered(self):
        run = self.manifest.acquisition.runs[0]
        selection = self.manifest.selection.runs[0]
        visual = self.manifest.visual_planning.plans[0]
        for outcomes in (run.shot_acquisitions[:-1], run.shot_acquisitions + run.shot_acquisitions[:1],
                         list(reversed(run.shot_acquisitions))):
            if outcomes == run.shot_acquisitions:
                continue
            with self.subTest(outcomes=outcomes), self.assertRaises(ValueError):
                project_placements(selection, visual, replace(run, shot_acquisitions=outcomes))

    def test_materialization_rules(self):
        run = self.manifest.acquisition.runs[0]
        selection, visual = self.manifest.selection.runs[0], self.manifest.visual_planning.plans[0]
        for outcome in AcquisitionOutcome:
            bad = replace(run.shot_acquisitions[0], outcome=outcome,
                materialization_id=None if outcome == AcquisitionOutcome.MATERIALIZED else "injected")
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                project_placements(selection, visual, replace(run, shot_acquisitions=[bad] + run.shot_acquisitions[1:]))

    def test_all_unresolved_outcomes_preserved_without_inspection(self):
        # No registered acquisition adapter yields retained UNSUPPORTED_SOURCE evidence.
        m = build_acquisition(self.selected, storage=self.storage, spec=AcquisitionSpec())
        with patch.object(self.inspector, "inspect", side_effect=AssertionError()):
            result = self.build(m, acquisition_spec=AcquisitionSpec())
        self.assertEqual([p.acquisition_outcome for p in result.editing.plans[0].placements],
                         [s.outcome for s in m.acquisition.runs[0].shot_acquisitions])
        obs = current_edit_eligibility(result, storage=self.storage, acquisition_spec=AcquisitionSpec())
        self.assertFalse(obs.coverage_complete)
        self.assertEqual(obs.final_use_readiness, "NOT ESTABLISHED")
        self.assertEqual(obs.timing_state, TimingState.UNRESOLVED)

    def test_history_pointer_independent(self):
        m = self.build()
        for state, pointer in ((m.visual_planning, "active_creator_plan_id"),
                (m.selection, "active_creator_selection_id"), (m.acquisition, "active_creator_acquisition_id")):
            setattr(state, pointer, None)
        self.assertFalse(editing_errors(m))
        self.assertFalse(validate(m))

    def test_tampered_history_fails(self):
        m = self.build()
        p = m.editing.plans[0]
        variants = [replace(p, timing_state="TIMED"), replace(p, acquisition_id="wrong"),
            replace(p, placements=p.placements[:-1]), replace(p, placements=list(reversed(p.placements))),
            replace(p, output_signature="wrong"), replace(p, edit_spec=EditSpec(engine_version="2"))]
        if p.placements:
            bad = replace(p.placements[0], materialization_id="materialization:injected")
            variants.append(assign_identity(replace(p, placements=[bad] + p.placements[1:])))
        for variant in variants:
            m.editing.plans = [variant]
            with self.subTest(variant=variant):
                self.assertTrue(editing_errors(m))

    def test_no_inactive_reactivation(self):
        m = self.build()
        m.editing.active_creator_edit_plan_id = None
        before = deepcopy(m)
        with self.assertRaises(EditingError):
            self.build(m)
        self.assertEqual(m, before)

    def test_exact_active_reuse_and_artifacts(self):
        stage, m, execution = self.executed()
        self.assertTrue(stage.validate_reuse(m, execution))
        self.assertEqual(len(execution.artifacts), 2)
        self.assertEqual(self.build(m), m)
        artifacts = deepcopy(execution.artifacts)
        variants = [[], artifacts[:1], artifacts + artifacts[:1], list(reversed(artifacts)),
                    [replace(artifacts[0], signature="wrong"), artifacts[1]]]
        for variant in variants:
            execution.artifacts = variant
            with self.subTest(variant=variant):
                self.assertFalse(stage.validate_reuse(m, execution))
        execution.artifacts = artifacts
        for a in artifacts:
            self.assertNotIn(str(self.storage.root), a.reference)
            self.assertNotIn("http", a.reference)

    def test_capacity_preflight_and_reuse(self):
        stage, m, execution = self.executed()
        with patch("creator_studio.editing.engine.MAX_EDIT_PLANS", 1):
            self.assertEqual(self.build(m), m)
        with patch("creator_studio.editing.engine.MAX_EDIT_PLANS", 0), \
                patch.object(self.storage, "verify", side_effect=AssertionError("expensive verification")):
            with self.assertRaises(EditingError) as caught:
                self.build()
            self.assertEqual(caught.exception.code, "editing_capacity")

    def test_callback_changes_active_acquisition_fails_closed(self):
        def callback(path, control):
            self.manifest.acquisition.active_creator_acquisition_id = None
            return self.inspector.facts
        with patch.object(self.inspector, "inspect", side_effect=callback):
            with self.assertRaises(EditingError):
                self.build()
        self.assertEqual(self.manifest.editing, EditingState())

    def test_callback_changes_effective_review_fails_closed(self):
        def callback(path, control):
            run = self.manifest.selection.runs[0]
            revised = append_review(self.manifest, expected_selection_id=run.selection_id,
                expected_choice=run.shot_selections[0], expected_predecessor=None,
                status=ReviewStatus.APPROVED, locked=False)
            self.manifest.selection = revised.selection
            self.assertTrue(self.manifest.selection.reviews)
            return self.inspector.facts
        with patch.object(self.inspector, "inspect", side_effect=callback):
            with self.assertRaises(EditingError):
                self.build()
        self.assertEqual(self.manifest.editing, EditingState())

    def test_cancellation_at_every_checkpoint(self):
        counter = CountingControl()
        self.build(control=counter)
        for checkpoint in range(1, counter.count + 1):
            before = deepcopy(self.manifest)
            with self.subTest(checkpoint=checkpoint), self.assertRaises(Cancelled):
                self.build(control=CountingControl(checkpoint))
            self.assertEqual(self.manifest, before)

    def test_failure_atomicity(self):
        before = deepcopy(self.manifest)
        with patch.object(self.storage, "verify", side_effect=OSError("offline")):
            result = self.stage().execute(StageContext(self.manifest, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertEqual(self.manifest, before)

    def test_dependency_isolation(self):
        forbidden = {"PyQt", "PyQt6", "pipeline", "stock", "renderer", "requests", "httpx", "aiohttp", "subprocess", "ffmpeg", "ffprobe"}
        targets = list(Path("creator_studio/editing").glob("*.py")) + [Path("creator_studio/manifest/editing.py"), Path("creator_studio/manifest/editing_validation.py")]
        for target in targets:
            tree = ast.parse(target.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for name in names:
                    self.assertFalse(set(name.split(".")) & forbidden, (target, name))
                    self.assertNotIn("core.timeline", name)
        historical = targets[-1].read_text()
        for name in ("eligible_active_selection", "current_inputs", "current_usability", "acquisition.engine"):
            self.assertNotIn(name, historical)


    def test_not_selected_and_rights_blocked_coverage(self):
        from creator_studio.selection.engine import build_selection
        from creator_studio.retrieval.engine import build_retrieval
        intent = with_intent(build_visual_plan(build_semantic_story(content())))
        unresolved = build_selection(build_retrieval(intent))
        denied = OfflineProvider(permitted=False)
        denied_spec = AcquisitionSpec(providers=[denied.spec])
        for selected, providers, spec, expected in (
                (unresolved, (), AcquisitionSpec(), AcquisitionOutcome.NOT_SELECTED_UPSTREAM),
                (self.selected, (denied,), denied_spec, AcquisitionOutcome.RIGHTS_BLOCKED)):
            m = build_acquisition(selected, storage=self.storage, providers=providers, spec=spec)
            with patch.object(self.inspector, "inspect", side_effect=AssertionError("unexpected inspection")):
                result = self.build(m, acquisition_spec=spec)
            placements = result.editing.plans[0].placements
            self.assertEqual(len(placements), sum(len(u.planned_shots) for u in m.visual_planning.plans[0].units))
            self.assertTrue(all(p.acquisition_outcome == expected and p.materialization_id is None for p in placements))

    def test_same_materialization_keeps_distinct_placements(self):
        p = self.build().editing.plans[0]
        self.assertGreater(len(p.placements), 1)
        self.assertEqual(len({x.materialization_id for x in p.placements}), 1)
        self.assertEqual(len({x.placement_id for x in p.placements}), len(p.placements))

    def test_storage_relocation_excluded_from_identity(self):
        import shutil
        other = ManagedStorage(Path(self.temp.name) / "relocated")
        for asset in self.manifest.acquisition.assets:
            target = other.root / asset.object_key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.storage.root / asset.object_key, target)
        first = self.build()
        second = self.build(storage=other)
        self.assertEqual(first.editing, second.editing)
        self.assertEqual(self.stage().artifacts(first, first.editing.plans[0]),
            self.stage().artifacts(second, second.editing.plans[0]))

    def test_populated_canonical_domains_preserved(self):
        from creator_studio.manifest.models import (MediaReference, Provenance, Scene, Voice,
            SubtitleTrack, SubtitleSegment, AudioReference, TimelineReference)
        from creator_studio.manifest.rights import Rights
        m = deepcopy(self.manifest)
        m.media = [MediaReference(id="owned", reference="user-owned.wav",
            provenance=Provenance(rights=Rights.OWNED), final_eligible=True),
            MediaReference(id="unknown", final_eligible=False)]
        m.scenes = [Scene(id="scene", start=17.0, end=23.0, narration="Unrelated timing")]
        m.voice = Voice(audio_media_id="owned", alignment_reference="existing-alignment")
        m.subtitle_tracks = [SubtitleTrack(id="subtitles", segments=[SubtitleSegment(
            id="subtitle", scene_id="scene", start=17.0, end=23.0, original_text="Existing")])]
        m.audio = [AudioReference(id="audio", media_id="owned", scene_id="scene")]
        m.timeline = [TimelineReference(id="timeline", scene_id="scene", media_id="owned", start=17.0, end=23.0)]
        self.assertFalse(validate(m))
        before = deepcopy(m)
        result = self.build(m)
        self.assertTrue(boundary_unchanged(before, result))
        self.assertEqual(m, before)
        self.assertEqual(result.editing, self.build().editing)

    def test_changed_semantic_source_stales_without_invalidating_history(self):
        m = self.build()
        changed = content("Entirely different source text.", manifest=m)
        self.assertFalse(validate(changed))
        self.assertFalse(editing_errors(changed))
        with self.assertRaises(EditingError):
            self.build(changed)

    def test_effective_review_change_stales_existing_edit(self):
        stage, m, execution = self.executed()
        run = m.selection.runs[0]
        changed = append_review(m, expected_selection_id=run.selection_id,
            expected_choice=run.shot_selections[0], expected_predecessor=None,
            status=ReviewStatus.APPROVED, locked=True)
        self.assertFalse(validate(changed))
        self.assertFalse(stage.validate_reuse(changed, execution))
        with self.assertRaises(EditingError):
            self.build(changed)

    def test_return_boundary_rechecks_upstream(self):
        from creator_studio.manifest.validation import require_valid
        def mutate(proposal):
            require_valid(proposal)
            self.manifest.acquisition.active_creator_acquisition_id = None
        with patch("creator_studio.editing.engine.require_valid", side_effect=mutate):
            with self.assertRaises(EditingError):
                self.build()
        self.assertEqual(self.manifest.editing, EditingState())

    def test_active_plan_without_execution_cannot_reuse(self):
        m = self.build()
        with self.assertRaises(EditingError):
            self.build(m)

    def test_reuse_requires_exact_execution(self):
        stage, m, execution = self.executed()
        for changed in (replace(execution, stage_version="2"), replace(execution, stage_id="other"),
                replace(execution, dependency_signature="wrong"), replace(execution, status=StageStatus.FAILED)):
            self.assertFalse(stage.validate_reuse(m, changed))
        m.processing = []
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_bounds_historical(self):
        m = self.build()
        with patch("creator_studio.manifest.editing_validation.MAX_EDIT_PLANS", 0):
            self.assertTrue(editing_errors(m))
        with patch("creator_studio.manifest.editing_validation.MAX_PLACEMENTS_PER_PLAN", 0):
            self.assertTrue(editing_errors(m))
        with patch("creator_studio.manifest.editing_validation.MAX_TOTAL_HISTORICAL_PLACEMENTS", 0):
            self.assertTrue(editing_errors(m))
        self.assertEqual(MAX_EDIT_PLANS, 64)
        self.assertEqual(MAX_PLACEMENTS_PER_PLAN, 4096)
        self.assertEqual(MAX_TOTAL_HISTORICAL_PLACEMENTS, 65536)

    def test_historical_validation_never_calls_current_eligibility(self):
        m = self.build()
        with patch("creator_studio.acquisition.engine.current_inputs", side_effect=AssertionError()), \
                patch("creator_studio.acquisition.engine.current_usability", side_effect=AssertionError()), \
                patch("creator_studio.manifest.selection_validation.eligible_active_selection", side_effect=AssertionError()), \
                patch.object(self.storage, "verify", side_effect=AssertionError()):
            self.assertFalse(editing_errors(m))
            self.assertFalse(validate(m))

    def test_bytes_mutated_by_inspection_rejected(self):
        self.inspector.mutate = b"changed-by-inspector"
        with self.assertRaises(EditingError):
            self.build()
        self.assertEqual(self.manifest.editing, EditingState())

    def test_strict_decode_prohibits_timing_and_arbitrary_fields(self):
        p = self.build().editing.plans[0]
        for field in ("start", "end", "duration", "source_start", "source_end", "fps", "asset_id",
                "path", "url", "transition", "crop", "speed"):
            data = to_data(p.placements[0])
            data[field] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                decode(EditPlacement, data)
        data = to_data(p)
        data["timing_state"] = "TIMED"
        with self.assertRaises(ValueError):
            decode(EditPlan, data)


    def test_image_materialization_has_no_display_duration(self):
        from creator_studio.acquisition.provider import ResolvedRendition
        from creator_studio.manifest.acquisition import RenditionObservation, MediaFormat, MediaCodec
        from creator_studio.manifest.retrieval import VisualMediaKind
        from creator_studio.retrieval.models import CandidateProposal
        from creator_studio.manifest.visual import MediaFormPreference, assign_identity as visual_identity
        intent = with_intent(build_visual_plan(build_semantic_story(content())))
        visual = intent.visual_planning.plans[0]
        visual = visual_identity(replace(visual, units=[replace(u, planned_shots=[replace(shot,
            media_form_preference=MediaFormPreference.IMAGE_PREFERRED) for shot in u.planned_shots]) for u in visual.units]))
        intent.visual_planning.plans = [visual]
        intent.visual_planning.active_creator_plan_id = visual.visual_plan_id
        selected = selected_fixture(intent, [CandidateProposal("image:first", VisualMediaKind.IMAGE)])
        facts = replace(self.inspector.facts, media_kind=VisualMediaKind.IMAGE,
            media_format=MediaFormat.PNG, codec=MediaCodec.PNG, duration_seconds=None)
        self.inspector.facts = facts
        with patch.object(self.provider, "resolve", return_value=[ResolvedRendition(
                RenditionObservation("original", VisualMediaKind.IMAGE, 640, 480), object())]):
            m = build_acquisition(selected, storage=self.storage, providers=(self.provider,),
                inspector=self.inspector, spec=self.acquisition_spec)
        p = self.build(m).editing.plans[0]
        self.assertTrue(complete(p))
        self.assertTrue(all(x.acquisition_outcome == AcquisitionOutcome.MATERIALIZED for x in p.placements))
        self.assertNotIn("duration", to_data(p.placements[0]))

    def test_same_bytes_different_provenance_remain_distinguishable(self):
        from creator_studio.selection.engine import replace_choice
        from creator_studio.manifest.selection import (SelectedCandidateRef, SelectionSource,
            SelectionReason, shot_id, effective_output_signature)
        run = self.selected.selection.runs[0]
        choice = run.shot_selections[1]
        candidate = next(c for c in self.selected.retrieval.runs[0].candidates
                         if c.candidate_id != choice.selected_candidate.candidate_id)
        changed = replace(choice, selected_candidate=SelectedCandidateRef(candidate.candidate_id,
            candidate.metadata_fingerprint), source=SelectionSource.CREATOR, reason=SelectionReason.CREATOR_CHOICE)
        changed = replace(changed, shot_selection_id=shot_id(run.retrieval_id, run.selection_spec, changed))
        selected = replace_choice(self.selected, expected_selection_id=run.selection_id,
            expected_effective_output_signature=effective_output_signature(self.selected.selection, run),
            expected_choice=choice, replacement_choice=changed)
        m = build_acquisition(selected, storage=self.storage, providers=(self.provider,),
            inspector=self.inspector, spec=self.acquisition_spec)
        result = self.build(m)
        self.assertEqual(len(m.acquisition.assets), 1)
        self.assertEqual(len(m.acquisition.materializations), 2)
        placements = result.editing.plans[0].placements
        self.assertEqual(len({p.materialization_id for p in placements}), 2)
        # A self-signed cross-shot materialization replay still fails retained projection.
        plan = result.editing.plans[0]
        replay = replace(placements[0], materialization_id=placements[1].materialization_id)
        result.editing.plans = [assign_identity(replace(plan, placements=[replay] + placements[1:]))]
        result.editing.active_creator_edit_plan_id = result.editing.plans[0].edit_plan_id
        self.assertTrue(editing_errors(result))

    def test_cross_acquisition_replay_rejected(self):
        m = self.build()
        old = m.editing.plans[0]
        changed = build_acquisition(m, storage=self.storage, spec=AcquisitionSpec())
        run = next(r for r in changed.acquisition.runs if r.acquisition_id == changed.acquisition.active_creator_acquisition_id)
        expected = reconstruct(changed, run, EditSpec())
        forged = assign_identity(replace(expected, placements=old.placements))
        changed.editing.plans.append(forged)
        changed.editing.active_creator_edit_plan_id = forged.edit_plan_id
        self.assertTrue(editing_errors(changed))

    def test_newer_acquisition_does_not_silently_reuse(self):
        stage, m, execution = self.executed()
        changed = build_acquisition(m, storage=self.storage, spec=AcquisitionSpec())
        self.assertFalse(editing_errors(changed))
        self.assertFalse(stage.validate_reuse(changed, execution))
        with self.assertRaises(EditingError):
            self.build(changed)

    def test_projection_order_ignores_provider_digest_and_storage_order(self):
        m = deepcopy(self.manifest)
        m.acquisition.materializations.reverse()
        m.acquisition.assets.reverse()
        self.assertEqual(self.build(m).editing, self.build().editing)
        # Candidate/provider rank is not consulted by M69 projection.
        run = m.acquisition.runs[0]
        expected = reconstruct(m, run, EditSpec())
        with patch("creator_studio.manifest.selection_validation.baseline_choices", side_effect=AssertionError()):
            self.assertEqual(reconstruct(m, run, EditSpec()), expected)

    def test_signature_tampering_and_candidate_fingerprint_lineage(self):
        m = self.build()
        record = m.acquisition.materializations[0]
        selection = m.selection.runs[0]
        self.assertEqual(record.candidate_metadata_fingerprint,
            selection.shot_selections[0].selected_candidate.metadata_fingerprint)
        plan = m.editing.plans[0]
        for name in ("acquisition_output_signature", "upstream_binding_signature", "input_fingerprint", "edit_signature"):
            variant = assign_identity(replace(plan, **{name: "0" * 64}))
            m.editing.plans = [variant]
            m.editing.active_creator_edit_plan_id = variant.edit_plan_id
            with self.subTest(name=name):
                self.assertTrue(editing_errors(m))

    def test_placement_and_total_capacity_preflight(self):
        for name in ("MAX_PLACEMENTS_PER_PLAN", "MAX_TOTAL_HISTORICAL_PLACEMENTS"):
            with self.subTest(name=name), patch("creator_studio.editing.engine." + name, 0), \
                    patch.object(self.storage, "verify", side_effect=AssertionError("expensive verification")):
                with self.assertRaises(EditingError) as caught:
                    self.build()
                self.assertEqual(caught.exception.code, "editing_capacity")


    def test_semantic_review_change_preserves_historical_edit(self):
        from creator_studio.manifest.semantic import ReviewStatus as SemanticReview, output_signature
        m = self.build()
        document = replace(m.semantic.documents[0], review_status=SemanticReview.APPROVED)
        m.semantic.documents[0] = replace(document, output_signature=output_signature(document))
        self.assertFalse(validate(m))
        self.assertFalse(editing_errors(m))
        with self.assertRaises(EditingError):
            self.build(m)

    def test_visual_review_change_preserves_historical_edit(self):
        from creator_studio.manifest.visual import VisualReview, output_signature
        from creator_studio.manifest.semantic import ReviewStatus as SemanticReview
        m = self.build()
        visual = replace(m.visual_planning.plans[0], review=VisualReview(SemanticReview.APPROVED, True))
        m.visual_planning.plans[0] = replace(visual, output_signature=output_signature(visual))
        self.assertFalse(validate(m))
        self.assertFalse(editing_errors(m))
        with self.assertRaises(EditingError):
            self.build(m)


    def test_reuse_callback_cannot_replace_execution_state(self):
        stage, m, execution = self.executed()
        def callback(path, control):
            m.processing = []
            return self.inspector.facts
        with patch.object(self.inspector, "inspect", side_effect=callback):
            self.assertFalse(stage.validate_reuse(m, execution))

    def test_stage_dependencies_closed(self):
        self.assertEqual(self.stage().dependencies, ())
        self.assertEqual(self.stage(dependencies=("media_acquisition",)).dependencies, ("media_acquisition",))
        with self.assertRaises(EditingError):
            self.stage(dependencies=("render",))

    def test_dependency_iterables_normalized_once(self):
        for dependencies, expected in (((), ()),
                (("media_acquisition",), ("media_acquisition",)),
                (iter(("media_acquisition",)), ("media_acquisition",)),
                ((x for x in ("media_acquisition",)), ("media_acquisition",))):
            with self.subTest(kind=type(dependencies).__name__, expected=expected):
                stage = self.stage(dependencies=dependencies)
                self.assertEqual(stage.dependencies, expected)
                self.assertIsInstance(stage.dependencies, tuple)
                self.assertEqual((stage.stage_id, stage.stage_version), ("edit_planning", "1"))

        class OneShot:
            def __iter__(self):
                if getattr(self, "consumed", False):
                    raise AssertionError("dependency iterable consumed twice")
                self.consumed = True
                return iter(("media_acquisition",))

        self.assertEqual(self.stage(dependencies=OneShot()).dependencies, ("media_acquisition",))

    def test_invalid_dependency_iterables_rejected(self):
        for values in (("wrong_dependency",), ("media_acquisition", "wrong_dependency"),
                ("media_acquisition", "media_acquisition")):
            for factory in (tuple, iter, lambda values: (x for x in values)):
                with self.subTest(values=values, kind=factory.__name__), self.assertRaises(EditingError):
                    self.stage(dependencies=factory(values))

    def combined_execution(self, dependencies):
        from creator_studio.acquisition.stage import MediaAcquisitionStage
        from creator_studio.orchestrator import ProjectOrchestrator, StageOutcome, StageResult

        class MemoryRepository:
            def __init__(self, manifest):
                self.manifest = deepcopy(manifest)

            def load(self):
                return deepcopy(self.manifest)

            def validate(self, manifest):
                from creator_studio.manifest.validation import require_valid
                require_valid(manifest)

            def save(self, manifest):
                self.validate(manifest)
                self.manifest = deepcopy(manifest)

        acquisition = MediaAcquisitionStage(storage=self.storage, inspector=self.inspector,
            spec=self.acquisition_spec)
        manifest = self.manifest
        run = manifest.acquisition.runs[0]
        selection = manifest.selection.runs[0]

        class RetainedAcquisition:
            stage_id = "media_acquisition"
            stage_version = "1"
            dependencies = ()
            signature_inputs = acquisition.signature_inputs
            readiness = acquisition.readiness

            def execute(self, context):
                return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                    artifacts=acquisition.artifacts(context.manifest, run, selection)))

        repository = MemoryRepository(manifest)
        stage = self.stage(dependencies=dependencies)
        runner = ProjectOrchestrator(repository)
        runner.register(RetainedAcquisition())
        runner.register(stage)
        summary = runner.run()
        self.assertEqual([r.status for r in summary.results], [StageStatus.SUCCEEDED] * 2)
        return stage, repository.load(), summary.results[-1]

    def test_combined_iterables_execution_signature_and_reuse(self):
        baseline = None
        for factory in (tuple, iter, lambda values: (x for x in values)):
            with self.subTest(kind=factory.__name__):
                stage, manifest, execution = self.combined_execution(factory(("media_acquisition",)))
                upstream = next(s.execution for s in manifest.processing if s.stage == "media_acquisition")
                self.assertEqual(upstream.status, StageStatus.SUCCEEDED)
                self.assertTrue(upstream.artifacts)
                evidence = {"media_acquisition": signature({
                    "dependency_signature": upstream.dependency_signature,
                    "artifacts": upstream.artifacts, "metadata": upstream.metadata})}
                inputs = {"inputs": stage.signature_inputs(manifest), "configuration": {}}
                self.assertEqual(execution.dependency_signature,
                    dependency_signature("edit_planning", "1", inputs, evidence))
                self.assertNotEqual(execution.dependency_signature,
                    dependency_signature("edit_planning", "1", inputs, {}))
                self.assertTrue(stage.validate_reuse(manifest, execution))
                repeated = stage.execute(StageContext(manifest, CancellationToken(), 1, lambda *a: None))
                self.assertEqual(repeated.result.status, StageStatus.SUCCEEDED)
                observed = (stage.dependencies, execution.dependency_signature, execution.artifacts,
                    manifest.editing, stage._execution_binding(self.manifest))
                if baseline is None:
                    baseline = observed
                else:
                    self.assertEqual(observed, baseline)

                missing = deepcopy(manifest)
                missing.processing = [s for s in missing.processing if s.stage != "media_acquisition"]
                self.assertFalse(stage.validate_reuse(missing, execution))
                missing_execution = deepcopy(manifest)
                next(s for s in missing_execution.processing if s.stage == "media_acquisition").execution = None
                self.assertFalse(stage.validate_reuse(missing_execution, execution))
                changed = deepcopy(manifest)
                next(s for s in changed.processing if s.stage == "media_acquisition").execution.dependency_signature = "0" * 64
                self.assertFalse(stage.validate_reuse(changed, execution))
                tampered = deepcopy(manifest)
                retained = next(s for s in tampered.processing if s.stage == "edit_planning")
                retained.dependency_signature = retained.execution.dependency_signature = "0" * 64
                self.assertFalse(stage.validate_reuse(tampered, retained.execution))

if __name__ == "__main__":
    unittest.main()
