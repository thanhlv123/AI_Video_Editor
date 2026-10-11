"""Provider-neutral synchronous stage contracts. Payloads must contain no secrets."""
from dataclasses import dataclass
from enum import Enum
from threading import Event as ThreadEvent
from typing import Callable, Protocol
from ..manifest.models import ProjectManifest
from ..manifest.execution import (
    Artifact, ExecutionDiagnostic as Diagnostic, ExecutionRecord as StageResult,
    ExecutionStatus as StageStatus, Severity,
)


class Cancelled(Exception):
    """Cooperative cancellation, never a stage failure."""


class CancellationToken:
    def __init__(self):
        self._event = ThreadEvent()

    def cancel(self):
        self._event.set()

    @property
    def requested(self):
        return self._event.is_set()

    def check(self):
        if self.requested:
            raise Cancelled()


class ReadinessKind(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"
    SATISFIED = "already_satisfied"


@dataclass(frozen=True)
class Readiness:
    kind: ReadinessKind = ReadinessKind.READY
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1

    def __post_init__(self):
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")

    def allows(self, result: StageResult):
        return (result.status == StageStatus.FAILED and result.retryable
                and result.attempt < self.max_attempts)


@dataclass(frozen=True)
class Progress:
    project_id: str
    current_stage: str | None
    completed_stages: int
    total_stages: int
    status: str
    stage_fraction: float | None = None

    @property
    def project_fraction(self):
        return (self.completed_stages + (self.stage_fraction or 0)) / self.total_stages if self.total_stages else 1.0


class EventKind(str, Enum):
    PROJECT_STARTED = "project_started"
    STAGE_STARTED = "stage_started"
    STAGE_PROGRESS = "stage_progress"
    STAGE_SUCCEEDED = "stage_succeeded"
    STAGE_FAILED = "stage_failed"
    STAGE_CANCELLED = "stage_cancelled"
    STAGE_SKIPPED = "stage_skipped"
    STAGE_PENDING = "stage_pending"
    STAGE_BLOCKED = "stage_blocked"
    PROJECT_COMPLETED = "project_completed"
    PROJECT_FAILED = "project_failed"
    PROJECT_CANCELLED = "project_cancelled"


@dataclass(frozen=True)
class ExecutionEvent:
    kind: EventKind
    progress: Progress
    result: StageResult | None = None


@dataclass(frozen=True)
class StageContext:
    manifest: ProjectManifest
    cancellation: CancellationToken
    attempt: int
    report_progress: Callable[[float, str], None]


@dataclass
class ManifestUpdate:
    """Explicit proposed replacement, validated and committed only on success."""
    manifest: ProjectManifest


@dataclass
class StageOutcome:
    result: StageResult
    update: ManifestUpdate | None = None


class Stage(Protocol):
    stage_id: str
    stage_version: str
    dependencies: tuple[str, ...]

    def signature_inputs(self, manifest: ProjectManifest) -> object: ...
    def readiness(self, manifest: ProjectManifest) -> Readiness: ...
    def execute(self, context: StageContext) -> StageOutcome: ...


class ArtifactValidator(Protocol):
    def valid(self, manifest: ProjectManifest, artifacts: list[Artifact]) -> bool: ...


@dataclass(frozen=True)
class ExecutionSummary:
    project_id: str
    status: StageStatus
    results: tuple[StageResult, ...]
