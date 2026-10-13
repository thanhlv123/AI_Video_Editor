"""M82 authority-bound deterministic bounded raster sampling runtime."""

import ast
import inspect
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch

import creator_studio.bounded_raster_sampling as api
import creator_studio.bounded_raster_sampling.runtime as module
import creator_studio.png8_raster_observer as upstream_api

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


class BoundedRuntimeTests(unittest.TestCase):

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
            api.BoundedRasterSamplingRuntime()
        )

    def tearDown(self):
        try:
            self.source.release(
                self.snapshot
            )
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
            api.BoundedRasterOutcome.FAILURE,
        )

        self.assertEqual(
            result.failure_code.value,
            code,
        )

        self.assertIsNone(
            result.descriptor
        )
        self.assertIsNone(
            result.profile
        )
        self.assertIsNone(
            result.raster
        )

        api.validate_bounded_raster_result(
            result
        )

    def test_success_without_upscale(self):
        result = self.run_live()

        self.assertIs(
            result.outcome,
            api.BoundedRasterOutcome.SUCCESS,
        )

        self.assertEqual(
            result.descriptor,
            self.snapshot.descriptor,
        )

        self.assertEqual(
            result.raster.source_width,
            2,
        )

        self.assertEqual(
            result.raster.source_height,
            1,
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
            api.BoundedRasterPixelFormat.RGBA8,
        )

        self.assertIs(
            result.raster.sampling_method,
            api.BoundedRasterSamplingMethod.NEAREST_CENTER,
        )

        self.assertEqual(
            result.raster.pixels,
            bytes([
                1, 2, 3, 255,
                4, 5, 6, 255,
            ]),
        )

        api.validate_bounded_raster_result(
            result
        )

    def test_runtime_downsamples_large_axis(self):
        width = 2048

        row = bytes(
            index & 0xFF
            for index in range(
                width * 3
            )
        )

        data = make_png(
            2,
            width,
            [row],
            [0],
        )

        source, snapshot = capture(data)

        try:
            result = self.runtime.observe(
                source,
                snapshot,
            )

            self.assertIs(
                result.outcome,
                api.BoundedRasterOutcome.SUCCESS,
            )

            self.assertEqual(
                result.raster.source_width,
                2048,
            )

            self.assertEqual(
                result.raster.source_height,
                1,
            )

            self.assertEqual(
                result.raster.width,
                1024,
            )

            self.assertEqual(
                result.raster.height,
                1,
            )

            self.assertEqual(
                result.raster.stride,
                4096,
            )

            self.assertEqual(
                len(result.raster.pixels),
                4096,
            )

        finally:
            source.release(snapshot)

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

    def test_real_upstream_failures(self):
        cases = [
            b"wrong!!!",
            png(),
        ]

        for data in cases:
            with self.subTest(
                size=len(data)
            ):
                source, snapshot = capture(data)

                try:
                    self.failure(
                        self.runtime.observe(
                            source,
                            snapshot,
                        ),
                        "UPSTREAM_RASTER_FAILED",
                    )

                finally:
                    source.release(snapshot)

    def test_all_upstream_failure_mapping(self):
        mappings = [
            (
                upstream_api.PNG8RasterFailureCode.SNAPSHOT_AUTHORITY_INVALID,
                "SNAPSHOT_AUTHORITY_INVALID",
            ),
            (
                upstream_api.PNG8RasterFailureCode.PREFLIGHT_FAILED,
                "UPSTREAM_RASTER_FAILED",
            ),
            (
                upstream_api.PNG8RasterFailureCode.RASTER_INVALID,
                "UPSTREAM_RASTER_FAILED",
            ),
            (
                upstream_api.PNG8RasterFailureCode.RESOURCE_LIMIT_EXCEEDED,
                "RESOURCE_LIMIT_EXCEEDED",
            ),
            (
                upstream_api.PNG8RasterFailureCode.DEADLINE_EXCEEDED,
                "DEADLINE_EXCEEDED",
            ),
            (
                upstream_api.PNG8RasterFailureCode.INTERNAL_FAILURE,
                "INTERNAL_FAILURE",
            ),
        ]

        for code, expected in mappings:
            with self.subTest(
                code=code
            ):
                upstream = upstream_api.PNG8RasterResult(
                    outcome=(
                        upstream_api.PNG8RasterOutcome.FAILURE
                    ),
                    descriptor=None,
                    profile=None,
                    raster=None,
                    failure_code=code,
                )

                with patch.object(
                    self.runtime._raster,
                    "observe",
                    return_value=upstream,
                ):
                    self.failure(
                        self.run_live(),
                        expected,
                    )

    def test_upstream_descriptor_must_match_snapshot(self):
        other_data = make_png(
            2,
            2,
            [
                bytes([
                    9, 8, 7,
                    6, 5, 4,
                ])
            ],
            [0],
        )

        other_source, other_snapshot = capture(
            other_data
        )

        try:
            upstream = (
                upstream_api.PNG8RasterObservationRuntime()
                .observe(
                    other_source,
                    other_snapshot,
                )
            )

            self.assertIs(
                upstream.outcome,
                upstream_api.PNG8RasterOutcome.SUCCESS,
            )

            with patch.object(
                self.runtime._raster,
                "observe",
                return_value=upstream,
            ):
                self.failure(
                    self.run_live(),
                    "SNAPSHOT_AUTHORITY_INVALID",
                )

        finally:
            other_source.release(
                other_snapshot
            )

    def test_concurrent_gate(self):
        entered = Event()
        finish = Event()
        results = []

        original = (
            self.runtime._raster.observe
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
            self.runtime._raster,
            "observe",
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
            api.BoundedRasterOutcome.SUCCESS,
        )

        self.assertIs(
            self.run_live().outcome,
            api.BoundedRasterOutcome.SUCCESS,
        )

    def test_deadline_and_recovery(self):
        calls = [0]

        def clock():
            calls[0] += 1

            if calls[0] < 3:
                return 0

            return 31

        with patch.object(
            module,
            "monotonic",
            side_effect=clock,
        ):
            self.failure(
                self.run_live(),
                "DEADLINE_EXCEEDED",
            )

        self.assertIs(
            self.run_live().outcome,
            api.BoundedRasterOutcome.SUCCESS,
        )

    def test_exception_mapping_and_recovery(self):
        with patch.object(
            module,
            "_sample",
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
            "_sample",
            side_effect=MemoryError(),
        ):
            self.failure(
                self.run_live(),
                "RESOURCE_LIMIT_EXCEEDED",
            )

        self.assertIs(
            self.run_live().outcome,
            api.BoundedRasterOutcome.SUCCESS,
        )

    def test_invalid_upstream_report_is_internal(self):
        with patch.object(
            self.runtime._raster,
            "observe",
            return_value=Hostile(),
        ):
            self.failure(
                self.run_live(),
                "INTERNAL_FAILURE",
            )

        self.assertIs(
            self.run_live().outcome,
            api.BoundedRasterOutcome.SUCCESS,
        )

    def test_baseexception_not_swallowed(self):
        with patch.object(
            module,
            "_sample",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.run_live()

        self.assertIs(
            self.run_live().outcome,
            api.BoundedRasterOutcome.SUCCESS,
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
                    api.BoundedRasterSamplingRuntime.observe
                ).parameters
            ),
            (
                "self",
                "runtime",
                "snapshot",
            ),
        )

        self.assertIn(
            "BoundedRasterSamplingRuntime",
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
                            for alias in node.names
                        )
                    )

                if isinstance(
                    node,
                    ast.ImportFrom,
                ):
                    self.assertFalse(
                        any(
                            part in forbidden_imports
                            for part in (
                                node.module or ""
                            ).split(".")
                        )
                    )


if __name__ == "__main__":
    unittest.main()