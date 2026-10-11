"""Offline orchestration contracts; fake engines exist only in this test module."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from creator_studio.manifest import load, save, signature, validate
from creator_studio.manifest.codec import to_data
from creator_studio.manifest.models import ProjectManifest, ProcessingState, Status
from creator_studio.manifest import PersistenceError
from unittest.mock import patch
from creator_studio.orchestrator import (
    Artifact, CancellationToken, Diagnostic, EventKind, ManifestRepository,
    ManifestUpdate, ProjectOrchestrator, Readiness, ReadinessKind, RetryPolicy,
    Severity, StageGraph, StageOutcome, StageResult, StageStatus, record_result,
)


class FakeStage:
    def __init__(self, stage_id, dependencies=(), *, version="1", action=None,
                 readiness=ReadinessKind.READY):
        self.stage_id = stage_id
        self.dependencies = dependencies
        self.stage_version = version
        self.action = action
        self.readiness_kind = readiness
        self.calls = []

    def signature_inputs(self, manifest):
        return {"script": manifest.content.script}

    def readiness(self, manifest):
        return Readiness(self.readiness_kind)

    def execute(self, context):
        self.calls.append(context.attempt)
        context.report_progress(0.5, "Working")
        if self.action:
            return self.action(self, context)
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                                       artifacts=[Artifact("logical/output", signature("output"))]))


def failure(stage, context, retryable=True):
    return StageOutcome(StageResult(stage.stage_id, stage.stage_version, StageStatus.FAILED,
                                   retryable=retryable,
                                   diagnostics=[Diagnostic(stage_id=stage.stage_id, retryable=retryable)]))


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "Dự án.json"
        save(ProjectManifest("Orchestrator"), self.path)
        self.repo = ManifestRepository(self.path)

    def runner(self, *stages, **kwargs):
        runner = ProjectOrchestrator(self.repo, **kwargs)
        for stage in stages:
            runner.register(stage)
        return runner

    def test_registration(self):
        runner = self.runner(FakeStage("a"))
        self.assertEqual(runner.states, {"a": StageStatus.PENDING})

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            self.runner(FakeStage("a"), FakeStage("a"))

    def test_missing_dependency(self):
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.runner(FakeStage("a", ("missing",))).run()
        self.assertEqual(before, self.path.read_bytes())

    def test_cycle(self):
        with self.assertRaises(ValueError):
            self.runner(FakeStage("a", ("b",)), FakeStage("b", ("a",))).run()

    def test_self_cycle(self):
        with self.assertRaises(ValueError):
            self.runner(FakeStage("a", ("a",))).run()

    def test_deterministic_order(self):
        for order in (("c", "b", "a"), ("a", "c", "b")):
            graph = StageGraph()
            for key in order:
                graph.register(FakeStage(key, ("a",) if key == "c" else ()))
            self.assertEqual(graph.order(), ("a", "b", "c"))

    def test_success_multistage(self):
        summary = self.runner(FakeStage("b", ("a",)), FakeStage("a")).run()
        self.assertEqual(summary.status, StageStatus.SUCCEEDED)
        self.assertEqual([r.stage_id for r in summary.results], ["a", "b"])
        self.assertTrue(all(r.attempt == 1 for r in summary.results))

    def test_failure_blocks_dependents_and_independent_continues(self):
        dependent, independent = FakeStage("b", ("a",)), FakeStage("c")
        summary = self.runner(FakeStage("a", action=failure), dependent, independent).run()
        self.assertEqual([r.status for r in summary.results],
                         [StageStatus.FAILED, StageStatus.BLOCKED, StageStatus.SUCCEEDED])
        self.assertEqual(dependent.calls, [])
        self.assertEqual(independent.calls, [1])

    def test_cancel_before(self):
        stage = FakeStage("a")
        runner = self.runner(stage)
        runner.cancel()
        summary = runner.run()
        self.assertEqual(summary.status, StageStatus.CANCELLED)
        self.assertEqual(summary.results[0].status, StageStatus.CANCELLED)
        self.assertEqual(stage.calls, [])

    def test_cancel_during(self):
        def action(stage, context):
            context.cancellation.cancel()
            context.cancellation.check()
        summary = self.runner(FakeStage("a", action=action), FakeStage("b")).run()
        self.assertEqual([r.status for r in summary.results], [StageStatus.CANCELLED] * 2)
        self.assertFalse(summary.results[0].retryable)

    def test_cancel_uncooperative_success_discarded(self):
        def action(stage, context):
            context.cancellation.cancel()
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED))
        self.assertEqual(self.runner(FakeStage("a", action=action)).run().results[0].status,
                         StageStatus.CANCELLED)

    def test_structured_result_and_diagnostic_roundtrip(self):
        summary = self.runner(FakeStage("a", action=failure)).run()
        result = summary.results[0]
        self.assertTrue(result.started_at and result.finished_at and result.dependency_signature)
        self.assertEqual(result.diagnostics[0].severity, Severity.ERROR)
        self.assertEqual(load(self.path).processing[0].execution, result)

    def test_progress_and_events(self):
        events = []
        self.runner(FakeStage("a"), on_event=events.append).run()
        self.assertEqual([e.kind for e in events], [EventKind.PROJECT_STARTED, EventKind.STAGE_STARTED,
                         EventKind.STAGE_PROGRESS, EventKind.STAGE_SUCCEEDED, EventKind.PROJECT_COMPLETED])
        self.assertEqual(events[2].progress.stage_fraction, 0.5)
        self.assertEqual(events[2].progress.project_fraction, 0.5)
        self.assertEqual(events[-1].progress.completed_stages, 1)

    def test_retry_accounting(self):
        def action(stage, context):
            if context.attempt < 3:
                return failure(stage, context)
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED))
        stage = FakeStage("a", action=action)
        summary = self.runner(stage, retry_policy=RetryPolicy(3)).run()
        self.assertEqual(stage.calls, [1, 2, 3])
        self.assertEqual(summary.results[0].attempt, 3)
        self.assertEqual(summary.status, StageStatus.SUCCEEDED)

    def test_retry_exhausted(self):
        stage = FakeStage("a", action=failure)
        summary = self.runner(stage, retry_policy=RetryPolicy(2)).run()
        self.assertEqual(stage.calls, [1, 2])
        self.assertEqual(summary.status, StageStatus.FAILED)

    def test_nonretryable(self):
        stage = FakeStage("a", action=lambda s, c: failure(s, c, False))
        self.runner(stage, retry_policy=RetryPolicy(3)).run()
        self.assertEqual(stage.calls, [1])

    def test_resume_survives_save_load_and_repeated_skip(self):
        stage = FakeStage("a")
        first = self.runner(stage).run().results[0]
        for _ in range(2):
            result = self.runner(stage).run().results[0]
            self.assertEqual(result.status, StageStatus.SKIPPED)
            self.assertEqual(result.dependency_signature, first.dependency_signature)
        self.assertEqual(stage.calls, [1])

    def test_input_change_invalidates(self):
        stage = FakeStage("a")
        first = self.runner(stage).run().results[0]
        manifest = load(self.path)
        manifest.content.script = "New script"
        save(manifest, self.path)
        second = self.runner(stage).run().results[0]
        self.assertNotEqual(first.dependency_signature, second.dependency_signature)
        self.assertEqual(stage.calls, [1, 1])

    def test_version_invalidates(self):
        stage = FakeStage("a")
        self.runner(stage).run()
        stage.stage_version = "2"
        self.assertEqual(self.runner(stage).run().results[0].status, StageStatus.SUCCEEDED)
        self.assertEqual(stage.calls, [1, 1])

    def test_config_invalidates(self):
        stage = FakeStage("a")
        self.runner(stage, configuration={"a": {"quality": 1}}).run()
        self.runner(stage, configuration={"a": {"quality": 2}}).run()
        self.assertEqual(stage.calls, [1, 1])

    def test_dependency_version_invalidates_descendants(self):
        a, b = FakeStage("a"), FakeStage("b", ("a",))
        self.runner(a, b).run()
        a.stage_version = "2"
        self.runner(a, b).run()
        self.assertEqual(b.calls, [1, 1])

    def test_failed_not_reused(self):
        stage = FakeStage("a", action=failure)
        self.runner(stage).run()
        self.runner(stage).run()
        self.assertEqual(stage.calls, [1, 1])

    def test_cancelled_not_reused(self):
        stage = FakeStage("a", action=lambda s, c: StageOutcome(StageResult("a", "1", StageStatus.CANCELLED)))
        self.runner(stage).run()
        stage.action = None
        self.assertEqual(self.runner(stage).run().results[0].status, StageStatus.SUCCEEDED)

    def test_artifact_validator_hook(self):
        class Reject:
            def valid(self, manifest, artifacts):
                return False
        stage = FakeStage("a")
        self.runner(stage).run()
        self.runner(stage, artifact_validator=Reject()).run()
        self.assertEqual(stage.calls, [1, 1])

    def test_manifest_valid_and_persistence_signatures_stable(self):
        self.runner(FakeStage("a")).run()
        manifest = load(self.path)
        self.assertEqual(validate(manifest), [])
        before = signature(manifest)
        save(manifest, self.path)
        self.assertEqual(before, signature(load(self.path)))

    def test_old_m61_processing_record_loads(self):
        manifest = load(self.path)
        manifest.processing.append(ProcessingState(stage="legacy"))
        data = to_data(manifest)
        del data["processing"][0]["execution"]
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(load(self.path).processing[0].execution)

    def test_stage_mutation_is_isolated(self):
        def action(stage, context):
            context.manifest.content.script = "Discarded"
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED))
        self.runner(FakeStage("a", action=action)).run()
        self.assertEqual(load(self.path).content.script, "")

    def test_explicit_update(self):
        def action(stage, context):
            context.manifest.content.script = "Accepted"
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED), ManifestUpdate(context.manifest))
        self.runner(FakeStage("a", action=action)).run()
        self.assertEqual(load(self.path).content.script, "Accepted")

    def test_invalid_update_rejected_without_content_change(self):
        def action(stage, context):
            context.manifest.project_id = "wrong"
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED), ManifestUpdate(context.manifest))
        before = load(self.path).project_id
        self.assertEqual(self.runner(FakeStage("a", action=action)).run().status, StageStatus.FAILED)
        self.assertEqual(load(self.path).project_id, before)

    def test_not_ready_does_not_execute(self):
        stage = FakeStage("a", readiness=ReadinessKind.NOT_READY)
        summary = self.runner(stage, FakeStage("b", ("a",))).run()
        self.assertEqual(summary.results[0].status, StageStatus.PENDING)
        self.assertEqual(summary.results[1].status, StageStatus.BLOCKED)
        self.assertEqual(stage.calls, [])

    def test_satisfied_without_record_is_not_reused(self):
        stage = FakeStage("a", readiness=ReadinessKind.SATISFIED)
        self.assertEqual(self.runner(stage).run().results[0].status, StageStatus.PENDING)
        self.assertEqual(stage.calls, [])

    def test_checkpoint(self):
        destination = Path(self.temp.name) / "snapshot.json"
        metadata = self.repo.checkpoint(destination, "Before execution")
        self.assertEqual(metadata.content_signature, signature(load(destination)))
        self.assertEqual(load(self.path).snapshots[0], metadata)

    def test_exception_payload_never_persisted_or_emitted(self):
        marker = "SYNTHETIC_PRIVATE_VALUE"
        def action(stage, context):
            raise RuntimeError(marker)
        events = []
        self.runner(FakeStage("a", action=action), on_event=events.append).run()
        self.assertNotIn(marker, self.path.read_text(encoding="utf-8"))
        self.assertNotIn(marker, repr(events))

    def test_credential_like_metadata_rejected(self):
        def action(stage, context):
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED,
                                            metadata=["token=synthetic-test-value"]))
        result = self.runner(FakeStage("a", action=action)).run().results[0]
        self.assertEqual(result.status, StageStatus.FAILED)
        self.assertNotIn("synthetic-test-value", self.path.read_text(encoding="utf-8"))

    def test_invalid_progress_is_failure(self):
        def action(stage, context):
            context.report_progress(float("nan"), "Working")
        self.assertEqual(self.runner(FakeStage("a", action=action)).run().status, StageStatus.FAILED)

    def test_observer_failure_does_not_retry_stage(self):
        def observer(event):
            raise RuntimeError("Observer failed")
        stage = FakeStage("a")
        self.assertEqual(self.runner(stage, on_event=observer).run().status, StageStatus.SUCCEEDED)
        self.assertEqual(stage.calls, [1])

    def test_retry_policy_validation(self):
        for count in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                RetryPolicy(count)

    def test_invalid_readiness_diagnostic_is_structured_failure(self):
        stage = FakeStage("a")
        stage.readiness = lambda m: Readiness(ReadinessKind.NOT_READY,
            (Diagnostic(stage_id="a", message="token=synthetic-test-value"),))
        self.assertEqual(self.runner(stage).run().status, StageStatus.FAILED)
        self.assertNotIn("synthetic-test-value", self.path.read_text(encoding="utf-8"))

    def test_invalid_artifact_is_not_saved(self):
        def action(stage, context):
            return StageOutcome(StageResult("a", "1", StageStatus.SUCCEEDED,
                                            artifacts=[Artifact("output", "bad-digest")]))
        self.assertEqual(self.runner(FakeStage("a", action=action)).run().status, StageStatus.FAILED)
        self.assertEqual(load(self.path).processing[0].execution.artifacts, [])

    def test_result_identity_mismatch_is_failure(self):
        stage = FakeStage("a", action=lambda s, c: StageOutcome(StageResult("other", "1", StageStatus.SUCCEEDED)))
        self.assertEqual(self.runner(stage).run().status, StageStatus.FAILED)

    def test_cancel_from_project_started_event(self):
        stage = FakeStage("a")
        runner = self.runner(stage)
        runner.on_event = lambda event: runner.cancel() if event.kind == EventKind.PROJECT_STARTED else None
        self.assertEqual(runner.run().status, StageStatus.CANCELLED)
        self.assertEqual(stage.calls, [])

    def test_failed_update_is_not_applied(self):
        def action(stage, context):
            context.manifest.content.script = "Discarded"
            outcome = failure(stage, context, False)
            outcome.update = ManifestUpdate(context.manifest)
            return outcome
        self.runner(FakeStage("a", action=action)).run()
        self.assertEqual(load(self.path).content.script, "")

    def test_save_failure_before_execution_does_not_run_engine(self):
        stage = FakeStage("a")
        with patch.object(self.repo, "save", side_effect=PersistenceError("synthetic failure")):
            with self.assertRaises(PersistenceError):
                self.runner(stage).run()
        self.assertEqual(stage.calls, [])

    def test_empty_project_execution(self):
        self.assertEqual(self.runner().run().status, StageStatus.SUCCEEDED)

    def test_persistence_boundaries_abort(self):
        from creator_studio.orchestrator.repository import PersistenceAbort
        cases = [(1, None, 0), (2, None, 1), (3, None, 1), (4, None, 0),
                 (3, failure, 1),
                 (3, lambda s, c: StageOutcome(StageResult("a", "1", StageStatus.CANCELLED)), 1)]
        for boundary, action, attempt in cases:
            with self.subTest(boundary=boundary, action=action):
                save(ProjectManifest("Boundary"), self.path)
                a, b = FakeStage("a", action=action), FakeStage("b")
                original = self.repo.save
                durable = [self.path.read_bytes()]
                count = [0]
                def failing(candidate):
                    count[0] += 1
                    if count[0] == boundary:
                        raise OSError("token=synthetic-private")
                    original(candidate)
                    durable[0] = self.path.read_bytes()
                with patch.object(self.repo, "save", side_effect=failing):
                    # Final status boundary uses a single-stage graph.
                    runner = self.runner(a, *([] if boundary == 4 else [b]), retry_policy=RetryPolicy(2))
                    with self.assertRaises(PersistenceAbort) as caught:
                        runner.run()
                self.assertEqual(caught.exception.attempt, attempt)
                self.assertNotIn("synthetic-private", repr(caught.exception.diagnostic))
                self.assertEqual(self.path.read_bytes(), durable[0])
                self.assertEqual(b.calls, [])
                self.assertEqual(count[0], boundary)
                if boundary == 3:
                    self.assertEqual(a.calls, [1])
                    self.assertEqual(load(self.path).processing[0].execution.attempt, 1)

    def test_persistence_after_second_attempt_preserves_attempt(self):
        from creator_studio.orchestrator.repository import PersistenceAbort
        stage = FakeStage("a", action=failure)
        original = self.repo.save
        count = [0]
        def failing(candidate):
            count[0] += 1
            if count[0] == 5:
                raise OSError("storage unavailable")
            original(candidate)
        with patch.object(self.repo, "save", side_effect=failing):
            with self.assertRaises(PersistenceAbort) as caught:
                self.runner(stage, retry_policy=RetryPolicy(3)).run()
        self.assertEqual(caught.exception.attempt, 2)
        self.assertEqual(stage.calls, [1, 2])
        self.assertEqual(load(self.path).processing[0].execution.attempt, 2)
        self.assertEqual(load(self.path).processing[0].execution.status, StageStatus.RUNNING)

    def test_terminal_single_save_owner(self):
        with patch.object(self.repo, "save", wraps=self.repo.save) as writes:
            self.runner(FakeStage("a")).run()
        terminal = [call.args[0].processing[0].execution for call in writes.call_args_list
                    if call.args[0].processing and call.args[0].status == Status.RUNNING
                    and call.args[0].processing[0].execution.status == StageStatus.SUCCEEDED]
        self.assertEqual(len(terminal), 1)
        self.assertEqual(writes.call_count, 4)

    def test_processing_consistency(self):
        self.runner(FakeStage("a")).run()
        baseline = load(self.path)
        for outer, inner in [(Status.FAILED, StageStatus.SUCCEEDED),
                             (Status.SUCCEEDED, StageStatus.FAILED),
                             (Status.CANCELLED, StageStatus.SUCCEEDED),
                             (Status.SUCCEEDED, StageStatus.CANCELLED),
                             (Status.RUNNING, StageStatus.SUCCEEDED)]:
            with self.subTest(outer=outer, inner=inner):
                manifest = deepcopy(baseline)
                manifest.processing[0].status = outer
                manifest.processing[0].execution.status = inner
                self.assertTrue(validate(manifest))
        for attribute, value in [("dependency_signature", signature("different")), ("stage_id", "other")]:
            manifest = deepcopy(baseline)
            setattr(manifest.processing[0].execution, attribute, value)
            self.assertTrue(validate(manifest))
        self.assertEqual(validate(baseline), [])

    def test_running_pending_records_not_reused(self):
        for status in (Status.RUNNING, Status.PENDING):
            stage = FakeStage("a")
            manifest = ProjectManifest("Incomplete")
            manifest.processing.append(ProcessingState(stage="a", status=status,
                execution=StageResult("a", "1", StageStatus(status.value))))
            save(manifest, self.path)
            self.assertEqual(self.runner(stage).run().results[0].status, StageStatus.SUCCEEDED)
            self.assertEqual(stage.calls, [1])

    def test_duplicate_stage_preflight_before_mutation(self):
        from creator_studio.orchestrator.repository import PreflightError
        manifest = load(self.path)
        manifest.processing = [ProcessingState(stage="a"), ProcessingState(stage="a")]
        self.assertEqual(validate(manifest), [])  # M61 compatibility
        save(manifest, self.path)
        before = self.path.read_bytes()
        a, b = FakeStage("a"), FakeStage("b")
        with patch.object(self.repo, "save", wraps=self.repo.save) as writes:
            with self.assertRaises(PreflightError) as caught:
                self.runner(a, b).run()
        self.assertEqual(caught.exception.diagnostic.code, "ambiguous_processing_stage")
        self.assertEqual(writes.call_count, 0)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(a.calls + b.calls, [])

    def test_registration_metadata_frozen(self):
        from creator_studio.orchestrator.repository import PreflightError
        for name, value in [("stage_id", "other"), ("stage_version", "2"), ("dependencies", ("missing",))]:
            stage = FakeStage("a")
            runner = self.runner(stage)
            setattr(stage, name, value)
            self.assertEqual(runner.graph.order(), ("a",))
            with self.assertRaises(PreflightError):
                runner.run()
            self.assertEqual(stage.calls, [])
        graph = StageGraph()
        graph.register(FakeStage("a"))
        with self.assertRaises(TypeError):
            graph.stages["b"] = FakeStage("b")
        with self.assertRaises(AttributeError):
            graph.stages["a"].stage_id = "other"

    def test_graph_registration_locked_during_run(self):
        runner = self.runner(FakeStage("a"))
        rejected = []
        def observer(event):
            if event.kind == EventKind.PROJECT_STARTED:
                try:
                    runner.graph.register(FakeStage("b"))
                except ValueError:
                    rejected.append(True)
                else:
                    rejected.append(False)
        runner.on_event = observer
        runner.run()
        self.assertEqual(rejected, [True])
        self.assertEqual(runner.graph.order(), ("a",))

    def test_cancelled_runner_can_run_again(self):
        stage = FakeStage("a")
        runner = self.runner(stage)
        runner.cancel()
        self.assertEqual(runner.run().status, StageStatus.CANCELLED)
        self.assertEqual(runner.run().status, StageStatus.SUCCEEDED)
        self.assertEqual(stage.calls, [1])

    def test_readiness_pending_event(self):
        for readiness in (ReadinessKind.NOT_READY, ReadinessKind.SATISFIED, ReadinessKind.BLOCKED):
            events = []
            summary = self.runner(FakeStage("a", readiness=readiness), on_event=events.append).run()
            expected = EventKind.STAGE_BLOCKED if readiness == ReadinessKind.BLOCKED else EventKind.STAGE_PENDING
            self.assertEqual(events[1].kind, expected)
            self.assertEqual(summary.status, StageStatus.FAILED)

    def test_artifact_validator_exception_controlled(self):
        class Broken:
            def valid(self, manifest, artifacts):
                raise RuntimeError("token=synthetic-private")
        stage = FakeStage("a")
        self.runner(stage).run()
        result = self.runner(stage, artifact_validator=Broken()).run().results[0]
        self.assertEqual(result.status, StageStatus.FAILED)
        self.assertEqual(stage.calls, [1])
        self.assertNotIn("synthetic-private", self.path.read_text())

    def test_dependency_artifact_and_metadata_invalidate(self):
        for field in ("artifacts", "metadata"):
            save(ProjectManifest("Signatures"), self.path)
            a, b = FakeStage("a"), FakeStage("b", ("a",))
            self.runner(a, b).run()
            manifest = load(self.path)
            record = manifest.processing[0].execution
            if field == "artifacts":
                record.artifacts[0].signature = signature("changed")
            else:
                record.metadata = ["changed"]
            save(manifest, self.path)
            result = self.runner(a, b).run()
            self.assertEqual(result.results[0].status, StageStatus.SKIPPED)
            self.assertEqual(b.calls, [1, 1])

    def test_multistage_repeated_reuse_roundtrip(self):
        a, b = FakeStage("a"), FakeStage("b", ("a",))
        self.runner(a, b).run()
        for _ in range(3):
            save(load(self.path), self.path)
            self.assertTrue(all(r.status == StageStatus.SKIPPED for r in self.runner(a, b).run().results))
        self.assertEqual(a.calls, [1])
        self.assertEqual(b.calls, [1])

    def test_checkpoint_registration_failure_reports_recovery(self):
        from creator_studio.orchestrator.repository import PersistenceAbort
        destination = Path(self.temp.name) / "recovery.json"
        before = self.path.read_bytes()
        with patch.object(self.repo, "save", side_effect=OSError("private")):
            with self.assertRaises(PersistenceAbort) as caught:
                self.repo.checkpoint(destination, "Recovery")
        self.assertEqual(caught.exception.checkpoint_path, str(destination))
        self.assertTrue(destination.exists())
        self.assertEqual(before, self.path.read_bytes())

    def declaration_case(self, boundary, field="dependencies", value=("missing",), status=StageStatus.SUCCEEDED):
        from creator_studio.orchestrator.graph import StageDeclarationError
        a, b = FakeStage("a"), FakeStage("b")
        def mutate():
            setattr(a, field, value)
        def observer(event):
            if event.kind == boundary:
                mutate()
        if boundary == "signature":
            def inputs(manifest):
                mutate()
                return {"script": "proposed"}
            a.signature_inputs = inputs
        elif boundary == "readiness":
            def readiness(manifest):
                mutate()
                return Readiness()
            a.readiness = readiness
        elif boundary == "execute":
            def action(stage, context):
                mutate()
                context.manifest.content.script = "PROPOSED_OUTPUT"
                return StageOutcome(StageResult("a", "1", status, retryable=status == StageStatus.FAILED,
                    metadata=["PROPOSED_METADATA"]), ManifestUpdate(context.manifest))
            a.action = action
        runner = self.runner(a, b, on_event=observer, retry_policy=RetryPolicy(3))
        with self.assertRaises(StageDeclarationError) as caught:
            runner.run()
        self.assertEqual(caught.exception.diagnostic.code, "stage_declaration_changed")
        self.assertEqual(caught.exception.diagnostic.stage_id, "a")
        self.assertEqual(caught.exception.diagnostic.context, [field])
        self.assertEqual(a.calls, [1] if boundary == "execute" else [])
        self.assertEqual(b.calls, [])
        durable = load(self.path)
        self.assertNotEqual(durable.status, Status.SUCCEEDED)
        self.assertNotIn("PROPOSED", self.path.read_text())
        if durable.processing:
            self.assertEqual(durable.processing[0].execution.status, StageStatus.RUNNING)
            self.assertEqual(durable.processing[0].execution.attempt, 1)
        self.assertFalse(runner._active)
        self.assertFalse(runner.graph._active)

    def test_started_identity_mutation_aborts(self):
        self.declaration_case(EventKind.STAGE_STARTED, "stage_id", "other")

    def test_started_version_mutation_aborts(self):
        self.declaration_case(EventKind.STAGE_STARTED, "stage_version", "2")

    def test_started_dependencies_mutation_aborts(self):
        self.declaration_case(EventKind.STAGE_STARTED)

    def test_signature_input_mutation_aborts(self):
        self.declaration_case("signature")

    def test_readiness_mutation_aborts(self):
        self.declaration_case("readiness")

    def test_execute_success_mutation_rejects_update(self):
        self.declaration_case("execute")

    def test_execute_retryable_mutation_rejects_result(self):
        self.declaration_case("execute", status=StageStatus.FAILED)

    def test_project_started_mutation_aborts(self):
        self.declaration_case(EventKind.PROJECT_STARTED)

    def test_progress_mutation_aborts(self):
        from creator_studio.orchestrator.graph import StageDeclarationError
        stage = FakeStage("a")
        runner = self.runner(stage, on_event=lambda e: setattr(stage, "stage_version", "2")
                             if e.kind == EventKind.STAGE_PROGRESS else None)
        with self.assertRaises(StageDeclarationError):
            runner.run()
        self.assertEqual(stage.calls, [1])
        self.assertEqual(load(self.path).processing[0].execution.status, StageStatus.RUNNING)

    def test_between_retry_attempts_mutation_aborts(self):
        from creator_studio.orchestrator.graph import StageDeclarationError
        stage, independent = FakeStage("a", action=failure), FakeStage("b")
        class MutatingPolicy:
            max_attempts = 3
            def allows(self, result):
                stage.dependencies = ("missing",)
                return True
        with self.assertRaises(StageDeclarationError):
            self.runner(stage, independent, retry_policy=MutatingPolicy()).run()
        self.assertEqual(stage.calls, [1])
        self.assertEqual(independent.calls, [])
        record = load(self.path).processing[0].execution
        self.assertEqual(record.attempt, 1)
        self.assertEqual(record.status, StageStatus.FAILED)
        self.assertTrue(record.retryable)

    def test_registered_signature_identity_authoritative(self):
        from creator_studio.manifest import dependency_signature
        stage = FakeStage("a", version="7")
        runner = self.runner(stage)
        descriptor = runner.graph.stages["a"]
        result = runner.run().results[0]
        self.assertEqual(result.dependency_signature, dependency_signature(
            descriptor.stage_id, descriptor.stage_version,
            {"inputs": {"script": ""}, "configuration": {}}, {}))
        stage.stage_id, stage.stage_version, stage.dependencies = "other", "99", ("missing",)
        self.assertEqual((descriptor.stage_id, descriptor.stage_version, descriptor.dependencies), ("a", "7", ()))
        self.assertEqual(runner.graph.order(), ("a",))

    def test_stdlib_and_foundation_only(self):
        root = Path(__file__).resolve().parents[1] / "creator_studio" / "orchestrator"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    self.assertIn(name.split(".")[0], sys.stdlib_module_names)


if __name__ == "__main__":
    unittest.main()
