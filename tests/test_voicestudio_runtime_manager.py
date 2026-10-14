from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creator_studio.tts.voicestudio_runtime import VoiceStudioLocalRuntimeManager


class VoiceStudioRuntimeManagerTests(unittest.TestCase):
    def test_environment_override_is_discovered(self):
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / "VoiceStudio.exe"
            exe.write_bytes(b"test")
            manager = VoiceStudioLocalRuntimeManager(
                environment={"VOICESTUDIO_EXE": str(exe)},
                launcher=lambda _: None,
            )
            self.assertEqual(manager.discover_executable(), exe.resolve())

    def test_candidate_ports_include_electron_fallbacks(self):
        manager = VoiceStudioLocalRuntimeManager(environment={})
        urls = manager.candidate_backend_urls()
        self.assertIn("http://127.0.0.1:3900", urls)
        self.assertIn("http://127.0.0.1:4900", urls)
        self.assertIn("http://127.0.0.1:19900", urls)

    def test_explicit_port_is_prioritized(self):
        manager = VoiceStudioLocalRuntimeManager(environment={"OMNIVOICE_PORT": "7777"})
        self.assertEqual(manager.candidate_backend_urls()[0], "http://127.0.0.1:7777")

    def test_discover_backend_can_choose_fallback_port(self):
        manager = VoiceStudioLocalRuntimeManager(environment={})
        with patch.object(
            manager,
            "_probe_backend",
            side_effect=lambda url, timeout_seconds: url.endswith(":4900"),
        ):
            self.assertEqual(manager.discover_backend_url(), "http://127.0.0.1:4900")

    def test_start_uses_discovered_executable(self):
        launched = []
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / "VoiceStudio.exe"
            exe.write_bytes(b"test")
            manager = VoiceStudioLocalRuntimeManager(
                environment={"VOICESTUDIO_EXE": str(exe)},
                launcher=lambda path: launched.append(path),
                min_restart_interval_seconds=60,
            )
            with patch.object(manager, "discover_backend_url", return_value=None):
                ok, detail = manager.start()
                self.assertTrue(ok, detail)
                self.assertEqual(launched, [exe.resolve()])

                ok2, detail2 = manager.start()
                self.assertTrue(ok2, detail2)
                self.assertEqual(len(launched), 1)

    def test_running_backend_does_not_launch_app_again(self):
        launched = []
        manager = VoiceStudioLocalRuntimeManager(environment={}, launcher=lambda p: launched.append(p))
        with patch.object(manager, "discover_backend_url", return_value="http://127.0.0.1:4900"):
            ok, detail = manager.start()
        self.assertTrue(ok, detail)
        self.assertEqual(launched, [])
        self.assertIn("4900", detail)

    def test_missing_install_returns_actionable_message(self):
        manager = VoiceStudioLocalRuntimeManager(environment={}, launcher=lambda _: None)
        with patch.object(manager, "discover_backend_url", return_value=None), patch.object(
            manager, "discover_executable", return_value=None
        ):
            ok, detail = manager.start()
        self.assertFalse(ok)
        self.assertIn("VOICESTUDIO_EXE", detail)


if __name__ == "__main__":
    unittest.main()
