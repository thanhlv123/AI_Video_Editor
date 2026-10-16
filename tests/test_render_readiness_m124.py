"""M124: render preflight is a mandatory, actionable automation gate."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from creator_studio.render_readiness import (
    RenderReadinessError,
    require_render_ready,
)


class RenderReadinessGateTests(TestCase):
    def test_ready_timeline_returns_report(self):
        expected = {"status": "ready", "issues": [], "summary": {}}
        with patch(
            "creator_studio.render_readiness.inspect_timeline",
            return_value=expected,
        ) as inspect:
            actual = require_render_ready("timeline.json", "project")
        self.assertIs(actual, expected)
        inspect.assert_called_once_with(Path("timeline.json"), Path("project"))

    def test_warnings_do_not_block_render(self):
        report = {
            "status": "ready",
            "issues": [{"severity": "warning", "code": "external_media"}],
        }
        with patch(
            "creator_studio.render_readiness.inspect_timeline",
            return_value=report,
        ):
            self.assertIs(require_render_ready("timeline.json", "project"), report)

    def test_blocked_media_has_actionable_message(self):
        report = {
            "status": "blocked",
            "issues": [
                {
                    "severity": "error",
                    "code": "missing_media",
                    "message": "visual[0] media file is missing.",
                    "action": "Restore the missing asset.",
                },
            ],
        }
        with patch(
            "creator_studio.render_readiness.inspect_timeline",
            return_value=report,
        ):
            with self.assertRaises(RenderReadinessError) as caught:
                require_render_ready("timeline.json", "project")
        self.assertIn("missing_media", str(caught.exception))
        self.assertIn("visual[0]", str(caught.exception))
        self.assertIn("Restore the missing asset.", str(caught.exception))

    def test_blocked_report_without_errors_is_safe(self):
        with patch(
            "creator_studio.render_readiness.inspect_timeline",
            return_value={"status": "blocked", "issues": []},
        ):
            with self.assertRaises(RenderReadinessError):
                require_render_ready("timeline.json", "project")

    def test_many_issues_have_bounded_diagnostics(self):
        issues = [
            {"severity": "error", "code": f"error_{i}", "message": "broken"}
            for i in range(9)
        ]
        with patch(
            "creator_studio.render_readiness.inspect_timeline",
            return_value={"status": "blocked", "issues": issues},
        ):
            with self.assertRaises(RenderReadinessError) as caught:
                require_render_ready("timeline.json", "project")
        message = str(caught.exception)
        self.assertIn("error_4", message)
        self.assertNotIn("error_5", message)
        self.assertIn("4 lỗi khác", message)


if __name__ == "__main__":
    import unittest
    unittest.main()
