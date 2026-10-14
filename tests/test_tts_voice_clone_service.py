from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.tts import (
    TTSProviderInfo,
    TTSProviderRegistry,
    TTSService,
    TTSVoice,
    TTSVoiceCloneResult,
)


class CloneProvider:
    @property
    def info(self):
        return TTSProviderInfo(
            provider_id="clone",
            display_name="Clone Provider",
            is_local=True,
            supports_voice_cloning=True,
        )

    def health_check(self):
        return True, "ok"

    def list_voices(self):
        return ()

    def synthesize(self, request):
        raise NotImplementedError

    def clone_voice(self, request):
        return TTSVoiceCloneResult(
            provider_id="clone",
            voice_id="voice-123",
            display_name=request.name,
            language=request.language,
            raw={"id": "voice-123", "name": request.name},
        )


class NoCloneProvider:
    @property
    def info(self):
        return TTSProviderInfo(
            provider_id="no-clone",
            display_name="No Clone",
            is_local=True,
            supports_voice_cloning=False,
        )

    def health_check(self):
        return True, "ok"

    def list_voices(self):
        return ()

    def synthesize(self, request):
        raise NotImplementedError


class TTSVoiceCloneServiceTests(unittest.TestCase):
    def test_clone_voice_goes_through_provider_neutral_service(self):
        registry = TTSProviderRegistry()
        registry.register(CloneProvider())
        service = TTSService(registry)

        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "ref.wav"
            audio.write_bytes(b"RIFF-test")
            result = service.clone_voice(
                provider_id="clone",
                name="My Voice",
                reference_audio=audio,
                ref_text="Hello",
                language="English",
            )

        self.assertEqual(result.voice_id, "voice-123")
        self.assertEqual(result.display_name, "My Voice")
        self.assertTrue(service.supports_voice_cloning("clone"))

    def test_non_clone_provider_is_rejected(self):
        registry = TTSProviderRegistry()
        registry.register(NoCloneProvider())
        service = TTSService(registry)

        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "ref.wav"
            audio.write_bytes(b"RIFF-test")
            with self.assertRaises(ValueError):
                service.clone_voice(
                    provider_id="no-clone",
                    name="My Voice",
                    reference_audio=audio,
                )


if __name__ == "__main__":
    unittest.main()
