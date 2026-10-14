from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from creator_studio.tts.models import TTSSynthesisRequest
from creator_studio.tts.providers import VoiceStudioLocalProvider


def make_wav_bytes(duration_seconds: float = 0.05, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frame_count = max(1, int(duration_seconds * sample_rate))
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buf.getvalue()


class FakeVoiceStudioHandler(BaseHTTPRequestHandler):
    speech_calls = 0
    clone_calls = 0
    speech_payloads = []

    def log_message(self, format, *args):
        pass

    def _send_json(self, status: int, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "version": "test"})
            return
        if self.path == "/.well-known/voicestudio-speech":
            self._send_json(200, {"protocol": "voicestudio.speech.v1"})
            return
        if self.path == "/v1/audio/voices":
            self._send_json(
                200,
                {
                    "voices": [
                        {"voice_id": "alloy", "name": "Alloy", "type": "openai_alias"},
                        {
                            "voice_id": "profile-1",
                            "name": "My Clone",
                            "type": "profile",
                            "language": "en",
                        },
                    ],
                    "engines": [],
                },
            )
            return
        if self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": "tts-1", "voicestudio": {"kind": "tts", "alias_for_active_engine": True}},
                        {"id": "omnivoice", "voicestudio": {"kind": "tts", "alias_for_active_engine": False}},
                        {"id": "kittentts", "voicestudio": {"kind": "tts", "alias_for_active_engine": False}},
                        {"id": "faster-whisper", "voicestudio": {"kind": "stt", "alias_for_active_engine": False}},
                    ],
                },
            )
            return
        if self.path == "/profiles":
            self._send_json(200, [{"id": "profile-1", "name": "My Clone"}])
            return
        self._send_json(404, {"detail": "not found"})

    def do_POST(self):
        if self.path == "/v1/audio/speech":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            assert len(payload["input"]) <= VoiceStudioLocalProvider.MAX_API_CHARS
            type(self).speech_calls += 1
            type(self).speech_payloads.append(payload)
            body = make_wav_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/profiles":
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            type(self).clone_calls += 1
            self._send_json(200, {"id": "clone-123", "name": "Clone", "kind": "clone"})
            return
        self._send_json(404, {"detail": "not found"})


class VoiceStudioLocalProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FakeVoiceStudioHandler.speech_calls = 0
        FakeVoiceStudioHandler.clone_calls = 0
        FakeVoiceStudioHandler.speech_payloads = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeVoiceStudioHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def provider(self):
        return VoiceStudioLocalProvider(base_url=f"http://127.0.0.1:{self.port}")

    def test_rejects_non_loopback_url(self):
        with self.assertRaises(ValueError):
            VoiceStudioLocalProvider(base_url="https://example.com")

    def test_health_and_profile_voice_listing(self):
        provider = self.provider()
        ok, detail = provider.health_check()
        self.assertTrue(ok, detail)
        voices = provider.list_voices_for_engine("omnivoice")
        self.assertEqual(voices[0].voice_id, "default")
        self.assertEqual(voices[1].voice_id, "profile-1")
        self.assertFalse(any(v.voice_id == "alloy" for v in voices))

    def test_kittentts_exposes_eight_real_presets(self):
        provider = self.provider()
        voices = provider.list_voices_for_engine("kittentts")
        self.assertEqual(
            [v.voice_id for v in voices],
            list(provider.KITTENTTS_VOICE_MAP.values()),
        )
        self.assertEqual(len(voices), 8)
        self.assertTrue(voices[0].display_name.startswith("Bella"))
        self.assertTrue(voices[1].display_name.startswith("Jasper"))

    def test_engine_listing_filters_out_stt_and_alias_duplicates(self):
        provider = self.provider()
        engines = provider.list_engines()
        ids = [e.engine_id for e in engines]
        self.assertIn("tts-1", ids)
        self.assertIn("omnivoice", ids)
        self.assertIn("kittentts", ids)
        self.assertNotIn("faster-whisper", ids)
        self.assertEqual(ids.count("tts-1"), 1)

    def test_kittentts_is_not_clone_capable(self):
        provider = self.provider()
        self.assertFalse(provider.engine_supports_voice_cloning("kittentts"))
        self.assertTrue(provider.engine_supports_voice_cloning("omnivoice"))

    def test_selected_model_and_native_kittentts_voice_are_sent_to_speech_api(self):
        provider = self.provider()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out.wav"
            provider.synthesize(
                TTSSynthesisRequest(
                    provider_id=provider.PROVIDER_ID,
                    voice_id="Bella",  # legacy/friendly input is normalized
                    text="Hello from KittenTTS.",
                    output_path=output,
                    speed=1.15,
                    model_id="kittentts",
                )
            )
        payload = FakeVoiceStudioHandler.speech_payloads[-1]
        self.assertEqual(payload["model"], "kittentts")
        self.assertEqual(payload["voice"], "expr-voice-2-f")
        self.assertEqual(payload["speed"], 1.15)

    def test_each_kittentts_display_name_maps_to_a_different_native_voice(self):
        provider = self.provider()
        seen = set()
        for display_name, expected_raw_id in provider.KITTENTTS_VOICE_MAP.items():
            native = provider._normalize_voice_id("kittentts", display_name)
            self.assertEqual(native, expected_raw_id)
            seen.add(native)
        self.assertEqual(len(seen), 8)

    def test_unknown_kittentts_voice_is_rejected_instead_of_silent_fallback(self):
        provider = self.provider()
        with self.assertRaises(ValueError):
            provider._normalize_voice_id("kittentts", "NotARealVoice")

    def test_long_text_is_chunked_and_merged(self):
        provider = self.provider()
        long_text = ("This is a sentence for chunking. " * 260).strip()
        before = FakeVoiceStudioHandler.speech_calls
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out.wav"
            result = provider.synthesize(
                TTSSynthesisRequest(
                    provider_id=provider.PROVIDER_ID,
                    voice_id="profile-1",
                    text=long_text,
                    output_path=output,
                    speed=1.0,
                    model_id="omnivoice",
                )
            )
            self.assertTrue(output.is_file())
            self.assertGreater(result.duration_seconds, 0)
            self.assertGreater(FakeVoiceStudioHandler.speech_calls - before, 1)
            self.assertEqual(result.model_id, "omnivoice")

    def test_clone_profile_uses_local_profiles_endpoint(self):
        provider = self.provider()
        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "ref.wav"
            audio.write_bytes(make_wav_bytes())
            payload = provider.create_clone_profile(
                name="Clone",
                reference_audio=audio,
                ref_text="Hello",
                language="en",
            )
            self.assertEqual(payload["id"], "clone-123")


if __name__ == "__main__":
    unittest.main()
