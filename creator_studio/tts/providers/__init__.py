from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["PiperProcessProvider", "VoiceStudioLocalProvider"]

# Keep provider imports lazy. The isolated Piper worker is started with
# ``python -m creator_studio.tts.providers.piper_worker`` from a minimal Piper
# virtual environment. Importing VoiceStudioLocalProvider here eagerly would
# also import ``requests`` and force that unrelated dependency into the Piper
# runtime. Lazy loading preserves provider isolation.
if TYPE_CHECKING:
    from .piper_provider import PiperProcessProvider
    from .voicestudio_provider import VoiceStudioLocalProvider


def __getattr__(name: str) -> Any:
    if name == "PiperProcessProvider":
        from .piper_provider import PiperProcessProvider

        return PiperProcessProvider
    if name == "VoiceStudioLocalProvider":
        from .voicestudio_provider import VoiceStudioLocalProvider

        return VoiceStudioLocalProvider
    raise AttributeError(name)
