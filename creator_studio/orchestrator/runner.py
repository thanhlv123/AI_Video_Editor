"""Sequential coordination only; engines own all domain work."""
from copy import deepcopy
import math
from ..manifest import dependency_signature, signature
from ..manifest.models import Status, utc_now
from .contracts import (
    ArtifactValidator, CancellationToken, Cancelled, Diagnostic, EventKind,
    ExecutionEvent, ExecutionSummary, Progress, ReadinessKind, RetryPolicy,
    StageContext, StageOutcome, StageResult, StageStatus,
)
from .graph import StageGraph, StageDeclarationError
from .repository import record_project_status, record_result, StageUpdateError, PersistenceAbort, PreflightError


class ReferenceArtifactValidator:
    """Foundation only: structural references, not file existence/integrity checks."""
    def valid(self, manifest, artifacts):
        return all(a.reference.strip() and len(a.signature) == 64 for a in artifacts)


class ProjectOrchestrator:
    def __init__(self, repository, *, retry_policy=RetryPolicy(), artifact_validator=None,
                 on_event=None, configuration=None):
        self.repository = repository
        self.retry_policy = retry_policy
        self.artifact_validator: ArtifactValidator = artifact_validator or ReferenceArtifactValidator()
        self.on_event = on_event
        self.configuration = deepcopy(configuration or {})
        signature(self.configuration)  # Require deterministic structured configuration.
        self.graph = StageGraph()
        self.cancellation = CancellationToken()
        self.states: dict[str, StageStatus] = {}
        self._active = False

    def register(self, stage):
        if self._active:
            raise ValueError("Cannot register during execution")
        self.graph.register(stage)
        self.states[stage.stage_id] = StageStatus.PENDING

    def cancel(self):
        self.cancellation.cancel()

    def _emit(self, kind, manifest, completed, total, stage_id=None, result=None, fraction=None):
        if self.on_event:
            event = ExecutionEvent(kind, Progress(manifest.project_id, stage_id, completed,
                                                 total, kind.value.replace("_", " "), fraction),
                                   deepcopy(result))
            try:
                self.on_event(event)
            except Exception:
                # Observer errors must not retry engine work or corrupt persisted state.
                # Controllers own reporting of their callback failures.
                pass
            self.graph.preflight()

    def run(self):
        if self._active:
            raise ValueError("Execution already active")
        self.graph.preflight()
        order = self.graph.order()
        manifest = self.repository.load()
        self.repository.validate(manifest)
        for stage_id in order:
            if sum(state.stage == stage_id for state in manifest.processing) > 1:
                raise PreflightError("ambiguous_processing_stage")
        self._active = True
        self.graph._active = True
        try:
            return self._run(manifest, order)
        finally:
            self._active = False
            self.graph._active = False
            self.cancellation = CancellationToken()

    def _run(self, manifest, order):
        total = len(order)
        results = {}
        manifest = record_project_status(self.repository, manifest, Status.RUNNING)
        self._emit(EventKind.PROJECT_STARTED, manifest, 0, total)
        for stage_id in order:
            self.graph.preflight()
            stage = self.graph.stages[stage_id]
            result = StageResult(stage_id, stage.stage_version, StageStatus.PENDING)
            completed = len(results)
            update = None
            persisted = False
            if self.cancellation.requested:
                result.status = StageStatus.CANCELLED
            elif any(results[d].status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)
                     for d in stage.dependencies):
                result.status = StageStatus.BLOCKED
                result.diagnostics = [Diagnostic(code="dependency_blocked", stage_id=stage_id,
                                                 message="Required dependency did not succeed.")]
            else:
                try:
                    upstream = {d: signature({"dependency_signature": results[d].dependency_signature,
                                               "artifacts": results[d].artifacts,
                                               "metadata": results[d].metadata})
                                for d in stage.dependencies}
                    try:
                        inputs = stage.signature_inputs(deepcopy(manifest))
                    finally:
                        self.graph.preflight()
                    result.dependency_signature = dependency_signature(
                        stage_id, stage.stage_version,
                        {"inputs": inputs,
                         "configuration": self.configuration.get(stage_id, {})}, upstream)
                    previous_state = next((s for s in manifest.processing if s.stage == stage_id), None)
                    previous = previous_state.execution if previous_state else None
                    reusable = (previous_state is not None and previous_state.status == Status.SUCCEEDED
                                and previous is not None and previous.stage_id == stage_id
                                and previous.status in (StageStatus.SUCCEEDED, StageStatus.SKIPPED)
                                and previous.stage_version == stage.stage_version
                                and previous.dependency_signature == result.dependency_signature
                                and self.artifact_validator.valid(deepcopy(manifest), deepcopy(previous.artifacts)))
                    if reusable and callable(getattr(stage, "validate_reuse", None)):
                        # Optional domain output check supplements generic artifact validation.
                        try:
                            reusable = stage.validate_reuse(deepcopy(manifest), deepcopy(previous))
                        finally:
                            self.graph.preflight()
                    self.graph.preflight()
                    if reusable:
                        result = deepcopy(previous)
                        result.status = StageStatus.SKIPPED
                    else:
                        try:
                            readiness = stage.readiness(deepcopy(manifest))
                        finally:
                            self.graph.preflight()
                        result.diagnostics = list(readiness.diagnostics)
                        if readiness.kind == ReadinessKind.SATISFIED:
                            # No matching output record: satisfaction alone cannot authorize reuse.
                            result.status = StageStatus.PENDING
                            result.diagnostics.append(Diagnostic(code="outputs_unverified", stage_id=stage_id,
                                                                 message="Satisfied inputs require a reusable output record."))
                        elif readiness.kind != ReadinessKind.READY:
                            result.status = (StageStatus.BLOCKED if readiness.kind == ReadinessKind.BLOCKED
                                             else StageStatus.PENDING)
                        else:
                            self.states[stage_id] = StageStatus.READY
                            result, update, manifest = self._execute(stage, manifest, result, completed, total)
                            persisted = True
                except (PersistenceAbort, StageDeclarationError):
                    raise
                except Cancelled:
                    result.status = StageStatus.CANCELLED
                except Exception:
                    # Never persist exception strings, tracebacks or provider payloads.
                    result.status = StageStatus.FAILED
                    result.retryable = False
                    result.diagnostics = [Diagnostic(stage_id=stage_id)]
            self.graph.preflight()
            if not persisted:
                result.finished_at = utc_now()
            self.states[stage_id] = result.status
            try:
                if not persisted:
                    manifest = record_result(self.repository, manifest, result, update)
            except StageUpdateError:
                result = StageResult(stage_id, stage.stage_version, StageStatus.FAILED,
                                     dependency_signature=result.dependency_signature,
                                     finished_at=utc_now(), attempt=result.attempt,
                                     diagnostics=[Diagnostic(stage_id=stage_id)])
                manifest = record_result(self.repository, manifest, result)
                self.states[stage_id] = result.status
            results[stage_id] = result
            event = {StageStatus.SUCCEEDED: EventKind.STAGE_SUCCEEDED,
                     StageStatus.SKIPPED: EventKind.STAGE_SKIPPED,
                     StageStatus.CANCELLED: EventKind.STAGE_CANCELLED,
                     StageStatus.PENDING: EventKind.STAGE_PENDING,
                     StageStatus.FAILED: EventKind.STAGE_FAILED}.get(result.status, EventKind.STAGE_BLOCKED)
            self._emit(event, manifest, len(results), total, stage_id, result)
        values = tuple(results.values())
        if self.cancellation.requested or any(r.status == StageStatus.CANCELLED for r in values):
            status, event = Status.CANCELLED, EventKind.PROJECT_CANCELLED
        elif any(r.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED) for r in values):
            status, event = Status.FAILED, EventKind.PROJECT_FAILED
        else:
            status, event = Status.SUCCEEDED, EventKind.PROJECT_COMPLETED
        manifest = record_project_status(self.repository, manifest, status)
        self._emit(event, manifest, total, total)
        return ExecutionSummary(manifest.project_id, StageStatus(status.value), deepcopy(values))

    def _execute(self, stage, manifest, identity, completed, total):
        def progress(fraction, message):
            if not isinstance(fraction, (int, float)) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                raise ValueError("Progress must be between zero and one")
            # Use a controlled human-readable status, never arbitrary engine payloads.
            self._emit(EventKind.STAGE_PROGRESS, manifest, completed, total, stage.stage_id,
                       fraction=float(fraction))

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.graph.preflight()
            current = deepcopy(identity)
            current.attempt = attempt
            current.started_at = utc_now()
            current.status = StageStatus.RUNNING
            self.states[stage.stage_id] = StageStatus.RUNNING
            manifest = record_result(self.repository, manifest, current)
            self._emit(EventKind.STAGE_STARTED, manifest, completed, total, stage.stage_id, current)
            update = None
            try:
                self.cancellation.check()
                self.graph.preflight()
                try:
                    outcome = stage.execute(StageContext(deepcopy(manifest), self.cancellation, attempt, progress))
                finally:
                    self.graph.preflight()
                if not isinstance(outcome, StageOutcome):
                    raise ValueError("StageOutcome required")
                returned = outcome.result
                if (returned.stage_id != stage.stage_id or returned.stage_version != stage.stage_version
                        or returned.status not in (StageStatus.SUCCEEDED, StageStatus.FAILED, StageStatus.CANCELLED)):
                    raise ValueError("Invalid stage result identity/status")
                current.artifacts = deepcopy(returned.artifacts)
                current.diagnostics = deepcopy(returned.diagnostics)
                current.metadata = deepcopy(returned.metadata)
                current.retryable = returned.retryable
                current.status = returned.status
                update = outcome.update if current.status == StageStatus.SUCCEEDED else None
                self.cancellation.check()
            except StageDeclarationError:
                raise
            except Cancelled:
                current.status = StageStatus.CANCELLED
                current.retryable = False
                update = None
            except Exception:
                current.status = StageStatus.FAILED
                current.retryable = False
                current.diagnostics = [Diagnostic(stage_id=stage.stage_id)]
                update = None
            self.graph.preflight()
            current.finished_at = utc_now()
            # Validate proposals before permitting retries or final application.
            try:
                manifest = record_result(self.repository, manifest, current, update)
            except StageUpdateError:
                current.status = StageStatus.FAILED
                current.retryable = False
                current.artifacts = []
                current.metadata = []
                current.diagnostics = [Diagnostic(code="invalid_stage_update", stage_id=stage.stage_id,
                                                 message="Stage result or project update was invalid.")]
                update = None
                manifest = record_result(self.repository, manifest, current)
            # Update was already applied atomically with its result.
            update = None
            retry = self.retry_policy.allows(current)
            self.graph.preflight()
            if not retry:
                return current, update, manifest
        raise AssertionError("Retry policy exhausted without a result")
