from __future__ import annotations

from pathlib import Path

from .models import (
    TTSEngine,
    TTSSynthesisRequest,
    TTSSynthesisResult,
    TTSVoice,
    TTSVoiceCloneRequest,
    TTSVoiceCloneResult,
)
from .registry import TTSProviderRegistry


class TTSService:
    """Provider-neutral TTS application service.

    The GUI talks to this service only. Provider-specific capabilities such as
    engine discovery are optional and exposed through small capability methods,
    keeping Piper and future cloud/local providers interchangeable.
    """

    def __init__(self, registry: TTSProviderRegistry) -> None:
        self._registry = registry

    def list_providers(self):
        return self._registry.infos()

    def provider(self, provider_id: str):
        """Internal integration seam for desktop runtime orchestration."""
        return self._registry.get(provider_id)

    def health_check(self, provider_id: str) -> tuple[bool, str]:
        return self._registry.get(provider_id).health_check()

    def provider_info(self, provider_id: str):
        return self._registry.get(provider_id).info

    def supports_voice_cloning(self, provider_id: str) -> bool:
        return bool(self.provider_info(provider_id).supports_voice_cloning)

    def list_engines(self, provider_id: str) -> tuple[TTSEngine, ...]:
        provider = self._registry.get(provider_id)
        method = getattr(provider, "list_engines", None)
        if not callable(method):
            return ()
        return tuple(method())

    def engine_supports_voice_cloning(self, provider_id: str, engine_id: str | None) -> bool:
        provider = self._registry.get(provider_id)
        method = getattr(provider, "engine_supports_voice_cloning", None)
        if callable(method):
            return bool(method(engine_id))
        return bool(provider.info.supports_voice_cloning)

    def list_voices(self, provider_id: str, model_id: str | None = None) -> tuple[TTSVoice, ...]:
        provider = self._registry.get(provider_id)
        method = getattr(provider, "list_voices_for_engine", None)
        if callable(method):
            return tuple(method(model_id))
        return tuple(provider.list_voices())

    def synthesize(
        self,
        *,
        provider_id: str,
        voice_id: str,
        text: str,
        output_path: str | Path,
        speed: float = 1.0,
        volume: float = 1.0,
        speaker_id: int | None = None,
        model_id: str | None = None,
    ) -> TTSSynthesisResult:
        request = TTSSynthesisRequest(
            provider_id=provider_id,
            voice_id=voice_id,
            text=text,
            output_path=Path(output_path),
            speed=speed,
            volume=volume,
            speaker_id=speaker_id,
            model_id=model_id,
        )
        return self._registry.get(provider_id).synthesize(request)

    def clone_voice(
        self,
        *,
        provider_id: str,
        name: str,
        reference_audio: str | Path,
        ref_text: str = "",
        language: str = "Auto",
        instruct: str = "",
    ) -> TTSVoiceCloneResult:
        provider = self._registry.get(provider_id)
        if not bool(provider.info.supports_voice_cloning):
            raise ValueError(f"TTS provider does not support voice cloning: {provider_id}")
        clone_method = getattr(provider, "clone_voice", None)
        if not callable(clone_method):
            raise ValueError(f"TTS provider has no clone_voice implementation: {provider_id}")
        request = TTSVoiceCloneRequest(
            provider_id=provider_id,
            name=str(name or "").strip(),
            reference_audio=Path(reference_audio),
            ref_text=str(ref_text or ""),
            language=str(language or "Auto"),
            instruct=str(instruct or ""),
        )
        return clone_method(request)
