from __future__ import annotations

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creator_studio.youtube_reference import (
    YOUTUBE_REFERENCE_FILENAME,
    YouTubeReferenceRequestError,
    YouTubeReferenceService,
    _create_ipv4_connection,
)


class _FakeSocket:
    def __init__(self, family, socktype, proto):
        self.family = family
        self.socktype = socktype
        self.proto = proto
        self.timeout = None
        self.bound = None
        self.connected = None
        self.closed = False

    def settimeout(self, value):
        self.timeout = value

    def bind(self, value):
        self.bound = value

    def connect(self, value):
        self.connected = value

    def close(self):
        self.closed = True


class _ErrorTransport:
    def get_json(self, endpoint, params):
        raise YouTubeReferenceRequestError(
            "YouTube API timed out while connecting.",
            reason_code="timeout",
        )


def _write_inputs(root: Path):
    query = root / "visual_query_plan.json"
    stock = root / "stock_acquisition_manifest.json"
    query.write_text(
        json.dumps(
            {
                "plans": [
                    {
                        "scene_id": "scene_001",
                        "strategy": "search",
                        "primary_query": "Havana Cuba",
                        "queries": ["Havana Cuba"],
                        "duration": 5.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stock.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "stock": {
                            "status": "validated",
                            "selection": {"best_score": 0.679},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return query, stock


class YouTubeReferenceM11031Tests(unittest.TestCase):
    def test_ipv4_connector_requests_af_inet_only(self):
        fake_socket = _FakeSocket(socket.AF_INET, socket.SOCK_STREAM, 6)
        with patch("creator_studio.youtube_reference.socket.getaddrinfo") as gai, patch(
            "creator_studio.youtube_reference.socket.socket", return_value=fake_socket
        ):
            gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.217.112.4", 443))
            ]
            result = _create_ipv4_connection(("www.googleapis.com", 443), timeout=3.0)

        self.assertIs(result, fake_socket)
        self.assertEqual(gai.call_args.args[2], socket.AF_INET)
        self.assertEqual(fake_socket.connected, ("172.217.112.4", 443))
        self.assertEqual(fake_socket.timeout, 3.0)

    def test_request_error_is_persisted_without_api_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            query, stock = _write_inputs(root)
            report = YouTubeReferenceService(
                run_dir=root,
                query_plan_path=query,
                stock_manifest_path=stock,
                api_key="secret-key-that-must-never-be-written",
                transport=_ErrorTransport(),
            ).run()

            self.assertEqual(report.error_count, 1)
            raw = (root / YOUTUBE_REFERENCE_FILENAME).read_text(encoding="utf-8")
            self.assertNotIn("secret-key-that-must-never-be-written", raw)
            payload = json.loads(raw)
            scene = payload["scenes"][0]
            self.assertEqual(scene["status"], "error")
            self.assertEqual(scene["error_reason"], "timeout")
            self.assertIn("timed out", scene["error_message"])


if __name__ == "__main__":
    unittest.main()
