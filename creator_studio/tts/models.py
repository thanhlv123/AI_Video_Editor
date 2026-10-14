from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class TTSError(RuntimeError):
    """Base exception for TTS operations."""


class TTSProviderUnavailableError(TTSError):
    """Raised when a configured TTS provider is not available."""


class TTSSynthesisError(TTSError):
    """Raised when speech synthesis fails."""


@dataclass(frozen=True)
class TTSProviderInfo:
    provider_id: str
    display_name: str
    is_local: bool
    supports_voice_cloning: bool = False
    supports_preview: bool = True


@dataclass(frozen=True)
class TTSEngine:
    provider_id: str
    engine_id: str
    display_name: str
    supports_voice_cloning: bool = False
    is_alias: bool = False


@dataclass(frozen=True)
class TTSVoice:
    provider_id: str
    voice_id: str
    display_name: str
    language: str | None = None
    quality: str | None = None
    model_path: str | None = None
    config_path: str | None = None


@dataclass(frozen=True)
class TTSVoiceCloneRequest:
    provider_id: str
    name: str
    reference_audio: Path
    ref_text: str = ""
    language: str = "Auto"
    instruct: str = ""


@dataclass(frozen=True)
class TTSVoiceCloneResult:
    provider_id: str
    voice_id: str
    display_name: str
    language: str | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class TTSSynthesisRequest:
    provider_id: str
    voice_id: str
    text: str
    output_path: Path
    speed: float = 1.0
    volume: float = 1.0
    speaker_id: int | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class TTSSynthesisResult:
    provider_id: str
    voice_id: str
    output_path: Path
    duration_seconds: float
    byte_count: int
    model_id: str | None = None
