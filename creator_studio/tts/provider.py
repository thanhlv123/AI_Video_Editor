from __future__ import annotations

from typing import Protocol, Sequence

from .models import (
    TTSSynthesisRequest,
    TTSSynthesisResult,
    TTSVoice,
    TTSVoiceCloneRequest,
    TTSVoiceCloneResult,
)


class TTSProvider(Protocol):
    @property
    def info(self):
        ...

    def health_check(self) -> tuple[bool, str]:
        ...

    def list_voices(self) -> Sequence[TTSVoice]:
        ...

    def synthesize(self, request: TTSSynthesisRequest) -> TTSSynthesisResult:
        ...


class TTSVoiceCloneProvider(Protocol):
    @property
    def info(self):
        ...

    def clone_voice(self, request: TTSVoiceCloneRequest) -> TTSVoiceCloneResult:
        ...
