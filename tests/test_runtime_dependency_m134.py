"""M134 PyAV/faster-whisper compatibility regression tests."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PyAVCompatibilityRequirementsTests(unittest.TestCase):
    def test_runtime_requirements_pin_pyav_below_19(self):
        text = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8").lower()
        self.assertIn("av>=11,<19", text)

    def test_ci_requirements_match_pyav_runtime_range(self):
        text = (ROOT / "requirements-ci.txt").read_text(encoding="utf-8").lower()
        self.assertIn("av>=11,<19", text)


if __name__ == "__main__":
    unittest.main()
