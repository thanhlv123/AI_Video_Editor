from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_studio.tts import (
    TTSProviderInfo,
    TTSProviderRegistry,
    TTSService,
    TTSSynthesisResult,
    TTSVoice,
)
from creator_studio.tts.providers import PiperProcessProvider


class FakeProvider:
    @property
    def info(self):
        return TTSProviderInfo(
            provider_id="fake",
            display_name="Fake",
            is_local=True,
        )

    def health_check(self):
        return True, "ok"

    def list_voices(self):
        return (
            TTSVoice(
                provider_id="fake",
                voice_id="voice-1",
                display_name="Voice 1",
                language="en",
            ),
        )

    def synthesize(self, request):
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"fake")
        return TTSSynthesisResult(
            provider_id="fake",
            voice_id=request.voice_id,
            output_path=request.output_path,
            duration_seconds=1.0,
            byte_count=4,
        )


class TTSFoundationTests(unittest.TestCase):
    def test_registry_and_service_are_provider_neutral(self):
        registry = TTSProviderRegistry()
        registry.register(FakeProvider())
        service = TTSService(registry)

        self.assertEqual(service.list_providers()[0].provider_id, "fake")
        self.assertEqual(service.list_voices("fake")[0].voice_id, "voice-1")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "voice.wav"
            result = service.synthesize(
                provider_id="fake",
                voice_id="voice-1",
                text="Hello",
                output_path=output,
            )
            self.assertEqual(result.output_path, output)
            self.assertTrue(output.is_file())

    def test_duplicate_provider_rejected(self):
        registry = TTSProviderRegistry()
        registry.register(FakeProvider())
        with self.assertRaises(ValueError):
            registry.register(FakeProvider())

    def test_piper_voice_catalog_does_not_import_piper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            voices = root / "voices"
            voices.mkdir()

            model = voices / "en_US-demo-medium.onnx"
            config = voices / "en_US-demo-medium.onnx.json"
            model.write_bytes(b"dummy")
            config.write_text(
                '{"language": {"code": "en_US"}}',
                encoding="utf-8",
            )

            provider = PiperProcessProvider(
                python_executable=root / "missing-python.exe",
                voices_root=voices,
                project_root=root,
            )
            found = provider.list_voices()

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].voice_id, "en_US-demo-medium")
            self.assertEqual(found[0].language, "en_US")
            self.assertEqual(found[0].quality, "medium")


if __name__ == "__main__":
    unittest.main()
