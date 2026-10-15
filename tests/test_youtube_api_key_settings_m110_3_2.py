from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.api_key_manager import APIKeyManager


class _MemoryKeyring:
    def __init__(self):
        self.values = {}

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def get_password(self, service, username):
        return self.values.get((service, username))

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


class YouTubeAPIKeySettingsM11032Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.keyring = _MemoryKeyring()
        self.patcher = patch("config.api_key_manager.keyring", self.keyring)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_youtube_profile_is_builtin(self):
        manager = APIKeyManager(self.root)
        profile = manager.get_profile("youtube_data")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["name"], "YouTube Data API")
        self.assertEqual(profile["env_var"], "YOUTUBE_API_KEY")
        self.assertTrue(profile["enabled"])

    def test_runtime_environment_exports_credential(self):
        manager = APIKeyManager(self.root)
        manager.set_secret("youtube_data", "test-youtube-key")
        runtime = manager.runtime_environment()
        self.assertEqual(runtime.get("YOUTUBE_API_KEY"), "test-youtube-key")

    def test_secret_is_not_written_to_provider_json(self):
        manager = APIKeyManager(self.root)
        manager.set_secret("youtube_data", "never-write-this-secret")
        payload = manager.config_path.read_text(encoding="utf-8")
        self.assertNotIn("never-write-this-secret", payload)
        data = json.loads(payload)
        youtube = next(p for p in data["providers"] if p["id"] == "youtube_data")
        self.assertNotIn("secret", youtube)
        self.assertNotIn("api_key", youtube)

    def test_existing_config_is_upgraded_with_youtube_profile(self):
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "api_providers.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "providers": [
                        {
                            "id": "kie_ai",
                            "name": "KIE AI",
                            "env_var": "KIE_API_KEY",
                            "base_url": "",
                            "model": "gpt-6-luna",
                            "enabled": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        manager = APIKeyManager(self.root)
        profile = manager.get_profile("youtube_data")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["env_var"], "YOUTUBE_API_KEY")

    def test_disabled_youtube_profile_is_not_exported(self):
        manager = APIKeyManager(self.root)
        profile = manager.get_profile("youtube_data")
        profile["enabled"] = False
        manager.update_profile(profile)
        manager.set_secret("youtube_data", "test-youtube-key")
        self.assertNotIn("YOUTUBE_API_KEY", manager.runtime_environment())


if __name__ == "__main__":
    unittest.main()
