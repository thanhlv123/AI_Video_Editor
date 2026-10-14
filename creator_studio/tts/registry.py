from __future__ import annotations

from .models import TTSProviderInfo
from .provider import TTSProvider


class TTSProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, TTSProvider] = {}

    def register(self, provider: TTSProvider) -> None:
        provider_id = provider.info.provider_id.strip()
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        if provider_id in self._providers:
            raise ValueError(f"TTS provider already registered: {provider_id}")
        self._providers[provider_id] = provider

    def replace(self, provider: TTSProvider) -> None:
        provider_id = provider.info.provider_id.strip()
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> TTSProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"Unknown TTS provider: {provider_id}") from exc

    def infos(self) -> tuple[TTSProviderInfo, ...]:
        return tuple(provider.info for provider in self._providers.values())

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(self._providers.keys())
