"""Optional execution metadata; independent of orchestration and engine code."""
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ExecutionDiagnostic:
    severity: Severity = Severity.ERROR
    code: str = "operation_failed"
    message: str = "Stage operation failed."
    stage_id: str = ""
    context: list[str] = field(default_factory=list)
    retryable: bool = False


@dataclass
class Artifact:
    reference: str
    signature: str


@dataclass
class ExecutionRecord:
    stage_id: str
    stage_version: str
    status: ExecutionStatus
    dependency_signature: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    attempt: int = 0
    artifacts: list[Artifact] = field(default_factory=list)
    diagnostics: list[ExecutionDiagnostic] = field(default_factory=list)
    retryable: bool = False
    metadata: list[str] = field(default_factory=list)


def execution_errors(record):
    """Semantic checks beyond the strict codec; never echo rejected payloads."""
    errors = []
    identifier = r"[A-Za-z0-9_.:-]+"
    digest = r"[0-9a-f]{64}"
    if not re.fullmatch(identifier, record.stage_id) or not record.stage_version.strip():
        errors.append("Invalid stage identity/version")
    if record.attempt < 0:
        errors.append("Invalid attempt number")
    if record.dependency_signature and not re.fullmatch(digest, record.dependency_signature):
        errors.append("Invalid dependency signature")
    times = []
    for value in (record.started_at, record.finished_at):
        try:
            parsed = datetime.fromisoformat(value) if value else None
            if parsed is not None and parsed.tzinfo is None:
                raise ValueError()
            times.append(parsed)
        except ValueError:
            errors.append("Invalid execution timestamp")
    if len(times) == 2 and all(times) and times[1] < times[0]:
        errors.append("Execution finishes before it starts")
    texts = [record.stage_version, *record.metadata]
    for artifact in record.artifacts:
        if not artifact.reference.strip() or not re.fullmatch(digest, artifact.signature):
            errors.append("Invalid artifact reference/signature")
        texts.append(artifact.reference)
    for diagnostic in record.diagnostics:
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", diagnostic.code)
                or diagnostic.stage_id != record.stage_id):
            errors.append("Invalid diagnostic identity/code")
        texts.extend([diagnostic.message, *diagnostic.context])
    # Defense in depth, not a substitute for the engine's no-secrets contract.
    secret = r"(?i)(?:api[_ -]?key|token|password|secret|credential)\s*[=:]|bearer\s+\S+|\bsk-[A-Za-z0-9_-]{8,}|://[^/\s]+:[^/\s]+@"
    if any(re.search(secret, text) for text in texts):
        errors.append("Credential-like payload is forbidden")
    return errors
