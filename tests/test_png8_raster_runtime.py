"""M81 authority-bound PNG8 raster observation runtime."""

import ast
import inspect
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch

import creator_studio.png8_raster_observer as api
import creator_studio.png8_raster_observer.runtime as module

from creator_studio.source_snapshot import (
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
)
from tests.test_png8_raster_decoder import make_png
from tests.test_png8_structural_preflight import (
    capture,
    png,
)


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")

    def __repr__(self):
        raise AssertionError("hostile repr")

    def __eq__(self, other):
        raise AssertionError("hostile equality")


class RasterRuntimeTests(unittest.TestCase):

    def setUp(self):
        self.row = bytes([
            1, 2, 3,
            4, 5, 6,
        ])

        self.data = make_png(
            2,
            2,
            [self.row],
            [0],
        )

        self.source, self.snapshot = capture(
            self.data
        )

        self.runtime = (
            api.PNG8RasterObservationRuntime()
        )

    def tearDown(self):
        try:
            self.source.release(self.snapshot)
        except Exception:
            pass

    def run_live(self):
        return self.runtime.observe(
            self.source,
            self.snapshot,
        )

    def failure(self, result, code):
        self.assertIs(
            result.outcome,
            api.PNG8RasterOutcome.FAILURE,
        )

        self.assertEqual(
            result.failure_code.value,
            code,
        )

        self.assertIsNone(result.descriptor)
        self.assertIsNone(result.profile)
        self.assertIsNone(result.raster)

        api.validate_raster_result(result)

    def test_success_exact_rgba8(self):
        result = self.run_live()

        self.assertIs(
            result.outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

        self.assertEqual(
            result.descriptor,
            self.snapshot.descriptor,
        )

        self.assertEqual(
            result.profile.coded_width_px,
            2,
        )

        self.assertEqual(
            result.profile.coded_height_px,
            1,
        )

        self.assertEqual(
            result.profile.color_type,
            2,
        )

        self.assertEqual(
            result.raster.width,
            2,
        )

        self.assertEqual(
            result.raster.height,
            1,
        )

        self.assertEqual(
            result.raster.stride,
            8,
        )

        self.assertIs(
            result.raster.pixel_format,
            api.PNG8PixelFormat.RGBA8,
        )

        self.assertEqual(
            result.raster.pixels,
            bytes([
                1, 2, 3, 255,
                4, 5, 6, 255,
            ]),
        )

        api.validate_raster_result(result)

    def test_exact_authority_inputs(self):
        class RuntimeSubclass(
            SourceSnapshotRuntime
        ):
            pass

        class SnapshotSubclass(
            VerifiedSourceSnapshot
        ):
            pass

        cases = [
            (
                Hostile(),
                self.snapshot,
            ),
            (
                self.source,
                Hostile(),
            ),
            (
                self.source,
                self.snapshot.descriptor,
            ),
            (
                RuntimeSubclass(
                    str(Path.cwd())
                ),
                self.snapshot,
            ),
            (
                self.source,
                object.__new__(
                    SnapshotSubclass
                ),
            ),
        ]

        for runtime, snapshot in cases:
            with self.subTest(
                runtime=type(runtime),
                snapshot=type(snapshot),
            ):
                self.failure(
                    self.runtime.observe(
                        runtime,
                        snapshot,
                    ),
                    "SNAPSHOT_AUTHORITY_INVALID",
                )

    def test_foreign_and_released_snapshot(self):
        foreign = SourceSnapshotRuntime(
            str(Path.cwd())
        )

        self.failure(
            self.runtime.observe(
                foreign,
                self.snapshot,
            ),
            "SNAPSHOT_AUTHORITY_INVALID",
        )

        source, snapshot = capture(
            self.data
        )

        source.release(snapshot)

        self.failure(
            self.runtime.observe(
                source,
                snapshot,
            ),
            "SNAPSHOT_AUTHORITY_INVALID",
        )

    def test_preflight_failure_mapping(self):
        cases = [
            (
                b"wrong!!!",
                "PREFLIGHT_FAILED",
            ),
            (
                png()[:-1],
                "PREFLIGHT_FAILED",
            ),
        ]

        for data, expected in cases:
            with self.subTest(
                expected=expected
            ):
                source, snapshot = capture(data)

                try:
                    result = self.runtime.observe(
                        source,
                        snapshot,
                    )

                    self.failure(
                        result,
                        expected,
                    )

                finally:
                    source.release(snapshot)

    def test_structural_success_but_raster_invalid(self):
        source, snapshot = capture(
            png()
        )

        try:
            result = self.runtime.observe(
                source,
                snapshot,
            )

            self.failure(
                result,
                "RASTER_INVALID",
            )

        finally:
            source.release(snapshot)

    def test_reacquired_bytes_must_match_descriptor(self):
        original = (
            SourceSnapshotRuntime.snapshot_bytes
        )

        calls = [0]

        def access(runtime, snapshot):
            calls[0] += 1

            if calls[0] == 1:
                return original(
                    runtime,
                    snapshot,
                )

            return b"short"

        with patch.object(
            SourceSnapshotRuntime,
            "snapshot_bytes",
            autospec=True,
            side_effect=access,
        ):
            self.failure(
                self.run_live(),
                "SNAPSHOT_AUTHORITY_INVALID",
            )

        self.assertEqual(
            calls[0],
            2,
        )

        self.assertIs(
            self.run_live().outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

    def test_concurrent_gate(self):
        entered = Event()
        finish = Event()
        results = []

        original = (
            self.runtime._preflight.preflight
        )

        def blocked(runtime, snapshot):
            entered.set()

            if not finish.wait(5):
                raise AssertionError(
                    "timeout"
                )

            return original(
                runtime,
                snapshot,
            )

        with patch.object(
            self.runtime._preflight,
            "preflight",
            side_effect=blocked,
        ):
            thread = Thread(
                target=lambda: results.append(
                    self.run_live()
                )
            )

            thread.start()

            try:
                self.assertTrue(
                    entered.wait(5)
                )

                self.failure(
                    self.run_live(),
                    "RESOURCE_LIMIT_EXCEEDED",
                )

            finally:
                finish.set()
                thread.join(5)

        self.assertFalse(
            thread.is_alive()
        )

        self.assertIs(
            results[0].outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

        self.assertIs(
            self.run_live().outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

    def test_deadline_and_recovery(self):
        with patch.object(
            module,
            "monotonic",
            side_effect=[
                0,
                0,
                31,
            ],
        ):
            self.failure(
                self.run_live(),
                "DEADLINE_EXCEEDED",
            )

        self.assertIs(
            self.run_live().outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

    def test_exception_mapping_and_recovery(self):
        with patch.object(
            module,
            "_decode",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            self.failure(
                self.run_live(),
                "INTERNAL_FAILURE",
            )

        with patch.object(
            module,
            "_decode",
            side_effect=MemoryError(),
        ):
            self.failure(
                self.run_live(),
                "RESOURCE_LIMIT_EXCEEDED",
            )

        self.assertIs(
            self.run_live().outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

    def test_invalid_preflight_report_is_internal(self):
        with patch.object(
            self.runtime._preflight,
            "preflight",
            return_value=Hostile(),
        ):
            self.failure(
                self.run_live(),
                "INTERNAL_FAILURE",
            )

        self.assertIs(
            self.run_live().outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

    def test_baseexception_not_swallowed(self):
        with patch.object(
            module,
            "_decode",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.run_live()

        self.assertIs(
            self.run_live().outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

    def test_detached_report_is_not_authority(self):
        result = self.run_live()

        self.failure(
            self.runtime.observe(
                self.source,
                result,
            ),
            "SNAPSHOT_AUTHORITY_INVALID",
        )

    def test_public_api_and_static_boundary(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    api.PNG8RasterObservationRuntime.observe
                ).parameters
            ),
            (
                "self",
                "runtime",
                "snapshot",
            ),
        )

        self.assertIn(
            "PNG8RasterObservationRuntime",
            api.__all__,
        )

        package = Path(
            api.__file__
        ).parent

        forbidden_imports = {
            "PIL",
            "Pillow",
            "cv2",
            "imageio",
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "hashlib",
        }

        for path in package.glob("*.py"):
            tree = ast.parse(
                path.read_text(
                    encoding="utf-8"
                )
            )

            for node in ast.walk(tree):
                if isinstance(
                    node,
                    ast.Import,
                ):
                    self.assertFalse(
                        any(
                            alias.name.split(".")[0]
                            in forbidden_imports
                            for alias
                            in node.names
                        )
                    )

                if isinstance(
                    node,
                    ast.ImportFrom,
                ):
                    self.assertFalse(
                        any(
                            part
                            in forbidden_imports
                            for part
                            in (
                                node.module or ""
                            ).split(".")
                        )
                    )


if __name__ == "__main__":
    unittest.main()