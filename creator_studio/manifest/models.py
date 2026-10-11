"""Manifest V2 contracts. IDs are allocated once and persisted unchanged."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from .execution import ExecutionRecord
from .content import ContentRecord
from .semantic import SemanticState
from .visual import VisualState

SCHEMA_VERSION = 2


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Rights(str, Enum):
    OWNED = "OWNED"
    LICENSED = "LICENSED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    UNKNOWN = "UNKNOWN"


class InputKind(str, Enum):
    TEXT = "text"
    TXT = "txt"
    DOCX = "docx"
    VIDEO = "local_video"
    IMAGE = "local_image"
    AUDIO = "local_audio"
    VOICE = "voice"
    MUSIC = "music"
    REFERENCE_URL = "reference_url"


class MediaKind(str, Enum):
    STOCK = "remote_stock"
    LOCAL = "local"
    PROJECT = "project"
    LIBRARY = "library"
    VIRTUAL_SHOT = "virtual_shot"
    AI_IMAGE = "ai_image"
    AI_VIDEO = "ai_video"


class TrackKind(str, Enum):
    ORIGINAL = "original"
    REVIEW = "creator_review"


class Approval(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class VoiceKind(str, Enum):
    IMPORTED = "imported"
    GENERATED = "generated"


class AudioKind(str, Enum):
    MUSIC = "music"
    SFX = "sfx"
    AMBIENCE = "ambience"


class _NumericBoundary:
    def __post_init__(self):
        # Only schema floats are normalized; integer fields retain integer types.
        from .codec import normalize_float_fields
        normalize_float_fields(self)


@dataclass
class Content:
    script: str = ""
    script_type: InputKind = InputKind.TEXT
    source_language: str = "en"
    review_language: str = "vi"
    revision: int = 0
    records: list[ContentRecord] = field(default_factory=list)
    canonical_content_id: str | None = None


@dataclass
class InputSource:
    id: str = field(default_factory=new_id)
    kind: InputKind = InputKind.TEXT
    reference: str = ""
    media_id: str | None = None
    rights: Rights = Rights.REFERENCE_ONLY


@dataclass
class Provenance:
    provider: str | None = None
    provider_media_id: str | None = None
    source_url: str | None = None
    creator: str | None = None
    license_information: str | None = None
    rights: Rights = Rights.REFERENCE_ONLY


@dataclass
class MediaReference(_NumericBoundary):
    id: str = field(default_factory=new_id)
    kind: MediaKind = MediaKind.LOCAL
    reference: str = ""
    provenance: Provenance = field(default_factory=Provenance)
    final_eligible: bool = False
    source_media_id: str | None = None
    start: float | None = None
    end: float | None = None


@dataclass
class Scene(_NumericBoundary):
    id: str = field(default_factory=new_id)
    order: int = 0
    script_start: int | None = None
    script_end: int | None = None
    narration: str = ""
    start: float | None = None
    end: float | None = None
    visual_intent: str = ""
    status: Status = Status.PENDING
    revision: int = 0
    media_ids: list[str] = field(default_factory=list)


@dataclass
class Voice(_NumericBoundary):
    kind: VoiceKind = VoiceKind.IMPORTED
    provider: str | None = None
    language: str = "en"
    voice_id: str | None = None
    speed: float = 1.0
    style: str = ""
    status: Status = Status.PENDING
    audio_media_id: str | None = None
    alignment_reference: str | None = None


@dataclass
class SubtitleSegment(_NumericBoundary):
    id: str = field(default_factory=new_id)
    scene_id: str = ""
    start: float = 0.0
    end: float = 1.0
    original_text: str = ""
    translated_text: str | None = None
    confidence: float | None = None
    approval: Approval = Approval.PENDING
    original_locked: bool = False
    translation_locked: bool = False
    source_segment_id: str | None = None


@dataclass
class SubtitleTrack:
    id: str = field(default_factory=new_id)
    kind: TrackKind = TrackKind.ORIGINAL
    language: str = "en"
    segments: list[SubtitleSegment] = field(default_factory=list)


@dataclass
class AudioReference:
    id: str = field(default_factory=new_id)
    kind: AudioKind = AudioKind.MUSIC
    media_id: str = ""
    scene_id: str | None = None


@dataclass
class TimelineReference(_NumericBoundary):
    id: str = field(default_factory=new_id)
    scene_id: str = ""
    media_id: str = ""
    start: float = 0.0
    end: float = 1.0


@dataclass
class Diagnostic:
    # Controlled codes only: never persist raw exception messages or API payloads.
    code: str = "operation_failed"
    retryable: bool = False


@dataclass
class ProcessingState:
    id: str = field(default_factory=new_id)
    stage: str = ""
    status: Status = Status.PENDING
    dependency_signature: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    execution: ExecutionRecord | None = None


@dataclass(frozen=True)
class SnapshotMetadata:
    id: str
    project_id: str
    created_at: str
    label: str
    schema_version: int
    content_signature: str
    manifest_reference: str
    parent_snapshot_id: str | None = None


@dataclass
class ProjectManifest:
    project_name: str
    schema_version: int = SCHEMA_VERSION
    project_id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    status: Status = Status.PENDING
    content: Content = field(default_factory=Content)
    inputs: list[InputSource] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    media: list[MediaReference] = field(default_factory=list)
    voice: Voice = field(default_factory=Voice)
    subtitle_tracks: list[SubtitleTrack] = field(default_factory=list)
    audio: list[AudioReference] = field(default_factory=list)
    timeline: list[TimelineReference] = field(default_factory=list)
    processing: list[ProcessingState] = field(default_factory=list)
    snapshots: list[SnapshotMetadata] = field(default_factory=list)
    semantic: SemanticState = field(default_factory=SemanticState)
    visual_planning: VisualState = field(default_factory=VisualState)
