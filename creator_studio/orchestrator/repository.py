"""Orchestration-owned copy/validate/save boundary over Manifest V2."""
from copy import deepcopy
from pathlib import Path
from typing import Protocol
from ..manifest import load, save, require_valid, snapshot_metadata, ManifestValidationError
from ..manifest.models import ProjectManifest, ProcessingState, Status, Diagnostic, utc_now
from .contracts import StageResult, StageStatus, ManifestUpdate, Diagnostic as ExecutionDiagnostic
from ..manifest import PersistenceError


class PersistenceAbort(PersistenceError):
    """Run abort: no further writes or scheduling; payload excludes raw exceptions."""
    def __init__(self, boundary, stage_id="", attempt=0):
        self.boundary, self.stage_id, self.attempt = boundary, stage_id, attempt
        self.diagnostic = ExecutionDiagnostic(code="persistence_failed", stage_id=stage_id,
            message="Project storage failed; orchestration aborted.", context=[boundary])
        super().__init__(self.diagnostic.message)


class PreflightError(ValueError):
    def __init__(self, code):
        self.diagnostic = ExecutionDiagnostic(code=code, message="Orchestration preflight rejected project or stage declarations.")
        super().__init__(self.diagnostic.message)


def persist(repository, candidate, boundary, result=None):
    try:
        repository.save(candidate)
    except Exception:
        raise PersistenceAbort(boundary, result.stage_id if result else "",
                               result.attempt if result else 0) from None


class StageUpdateError(ValueError):
    """Invalid proposed content/result, distinct from persistence failure."""


class ProjectRepository(Protocol):
    def load(self) -> ProjectManifest: ...
    def validate(self, manifest: ProjectManifest) -> None: ...
    def save(self, manifest: ProjectManifest) -> None: ...


class ManifestRepository:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        return load(self.path)

    def validate(self, manifest):
        require_valid(manifest)

    def save(self, manifest):
        save(manifest, self.path)

    def checkpoint(self, path, label, parent_snapshot_id=None):
        """Save recovery content first, then register its M61 snapshot metadata."""
        if Path(path).resolve() == self.path.resolve():
            raise ValueError("Checkpoint must use a separate path")
        manifest = self.load()
        metadata = snapshot_metadata(manifest, label, str(path), parent_snapshot_id)
        if Path(path).exists():
            raise ValueError("Checkpoint destination already exists")
        save(manifest, path)
        manifest.snapshots.append(metadata)
        try:
            self.save(manifest)
        except Exception:
            # Keep recovery content and report its location explicitly.
            failure = PersistenceAbort("checkpoint_registration")
            failure.checkpoint_path = str(path)
            raise failure from None
        return metadata


def record_result(repository: ProjectRepository, manifest: ProjectManifest,
                  result: StageResult, update: ManifestUpdate | None = None):
    candidate = deepcopy(manifest)
    if update is not None:
        if result.status != StageStatus.SUCCEEDED:
            raise StageUpdateError("Only successful stages can update project content")
        proposed = update.manifest
        # Lifecycle, execution history and snapshots belong to orchestration.
        for name in ("project_id", "schema_version", "created_at", "updated_at",
                     "status", "processing", "snapshots"):
            if getattr(proposed, name) != getattr(manifest, name):
                raise StageUpdateError("Stage attempted to change orchestration-owned state")
        candidate = deepcopy(proposed)
    states = [s for s in candidate.processing if s.stage == result.stage_id]
    if len(states) > 1:
        raise StageUpdateError("Ambiguous stage execution history")
    state = states[0] if states else ProcessingState(stage=result.stage_id)
    if not states:
        candidate.processing.append(state)
    state.execution = deepcopy(result)
    state.dependency_signature = result.dependency_signature or None
    state.status = {
        StageStatus.PENDING: Status.PENDING, StageStatus.RUNNING: Status.RUNNING,
        StageStatus.SUCCEEDED: Status.SUCCEEDED, StageStatus.FAILED: Status.FAILED,
        StageStatus.CANCELLED: Status.CANCELLED,
        StageStatus.READY: Status.PENDING, StageStatus.BLOCKED: Status.PENDING,
        StageStatus.SKIPPED: Status.SUCCEEDED,
    }[result.status]
    state.diagnostics = [Diagnostic(d.code, d.retryable) for d in result.diagnostics]
    candidate.updated_at = utc_now()
    try:
        repository.validate(candidate)
    except ManifestValidationError:
        raise StageUpdateError("Invalid stage result or update") from None
    persist(repository, candidate, "stage_result", result)
    return candidate


def record_project_status(repository, manifest, status):
    candidate = deepcopy(manifest)
    candidate.status = status
    candidate.updated_at = utc_now()
    repository.validate(candidate)
    persist(repository, candidate, "project_" + status.value)
    return candidate
