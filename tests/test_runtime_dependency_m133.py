"""M133 runtime dependency regression tests."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts import m131_bootstrap


ROOT = Path(__file__).resolve().parents[1]


class WhisperRuntimeDependencyTests(unittest.TestCase):
    def test_runtime_requirements_include_faster_whisper(self):
        text = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8").lower()
        self.assertIn("faster-whisper", text)

    def test_ci_requirements_include_faster_whisper(self):
        text = (ROOT / "requirements-ci.txt").read_text(encoding="utf-8").lower()
        self.assertIn("faster-whisper", text)

    def test_bootstrap_probes_faster_whisper(self):
        self.assertIn("faster_whisper", m131_bootstrap.RUNTIME_IMPORTS)


if __name__ == "__main__":
    unittest.main()
