"""M83 authority-bound deterministic raster feature observation runtime."""

import ast
import inspect
from pathlib import Path
import struct
from threading import Event, Thread
import unittest
from unittest.mock import patch
import zlib

import creator_studio.bounded_raster_sampling as upstream_api
import creator_studio.raster_feature_observer as api
import creator_studio.raster_feature_observer.runtime as module

from creator_studio.source_snapshot import (
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
)
from tests.test_png8_structural_preflight import (
    capture,
    png,
)


SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk(kind, payload=b""):
    body = kind + payload

    return (
        struct.pack(
            ">I",
            len(payload),
        )
        + body
        + struct.pack(
            ">I",
            zlib.crc32(body) & 0xFFFFFFFF,
        )
    )


def rgba_png(width, height, pixels):
    if (
        type(width) is not int
        or type(height) is not int
        or type(pixels) is not bytes
        or width <= 0
        or height <= 0
        or len(pixels) != width * height * 4
    ):
        raise ValueError("fixture_invalid")

    raw = bytearray()
    stride = width * 4

    for y in range(height):
        raw.append(0)

        start = y * stride

        raw.extend(
            pixels[
                start:
                start + stride
            ]
        )

    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,
        6,
        0,
        0,
        0,
    )

    phys = struct.pack(
        ">IIB",
        7,
        7,
        0,
    )

    return (
        SIGNATURE
        + chunk(
            b"IHDR",
            ihdr,
        )
        + chunk(
            b"pHYs",
            phys,
        )
        + chunk(
            b"IDAT",
            zlib.compress(
                bytes(raw)
            ),
        )
        + chunk(
            b"IEND"
        )
    )


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")

    def __repr__(self):
        raise AssertionError("hostile repr")

    def __eq__(self, other):
        raise AssertionError("hostile equality")


class RasterFeatureRuntimeTests(unittest.TestCase):

    def setUp(self):
        self.pixels = bytes([
            10, 20, 30, 0,
            40, 50, 60, 128,
            70, 80, 90, 255,
            100, 110, 120, 255,
        ])

        self.data = rgba_png(
            2,
            2,
            self.pixels,
        )

        self.source, self.snapshot = capture(
            self.data
        )

        self.runtime = (
            api.RasterFeatureObservationRuntime()
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
            api.RasterFeatureOutcome.FAILURE,
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
            result.features
        )

        api.validate_raster_feature_result(
            result
        )

    def test_success(self):
        result = self.run_live()

        self.assertIs(
            result.outcome,
            api.RasterFeatureOutcome.SUCCESS,
        )

        self.assertEqual(
            result.descriptor,
            self.snapshot.descriptor,
        )

        self.assertEqual(
            result.features.source_width,
            2,
        )

        self.assertEqual(
            result.features.source_height,
            2,
        )

        self.assertEqual(
            result.features.width,
            2,
        )

        self.assertEqual(
            result.features.height,
            2,
        )

        self.assertEqual(
            result.features.pixel_count,
            4,
        )

        self.assertEqual(
            result.features.mean_rgba,
            (
                55,
                65,
                75,
                159,
            ),
        )

        self.assertEqual(
            result.features.min_rgba,
            (
                10,
                20,
                30,
                0,
            ),
        )

        self.assertEqual(
            result.features.max_rgba,
            (
                100,
                110,
                120,
                255,
            ),
        )

        self.assertEqual(
            result.features.alpha_zero_pixels,
            1,
        )

        self.assertEqual(
            result.features.alpha_partial_pixels,
            1,
        )

        self.assertEqual(
            result.features.alpha_opaque_pixels,
            2,
        )

        self.assertEqual(
            len(result.features.luma_grid),
            64,
        )

        api.validate_raster_feature_result(
            result
        )

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
                source, snapshot = capture(
                    data
                )

                try:
                    self.failure(
                        self.runtime.observe(
                            source,
                            snapshot,
                        ),
                        "UPSTREAM_RASTER_FAILED",
                    )

                finally:
                    source.release(
                        snapshot
                    )

    def test_all_upstream_failure_mapping(self):
        mappings = [
            (
                upstream_api.BoundedRasterFailureCode.SNAPSHOT_AUTHORITY_INVALID,
                "SNAPSHOT_AUTHORITY_INVALID",
            ),
            (
                upstream_api.BoundedRasterFailureCode.UPSTREAM_RASTER_FAILED,
                "UPSTREAM_RASTER_FAILED",
            ),
            (
                upstream_api.BoundedRasterFailureCode.SAMPLING_INVALID,
                "UPSTREAM_RASTER_FAILED",
            ),
            (
                upstream_api.BoundedRasterFailureCode.RESOURCE_LIMIT_EXCEEDED,
                "RESOURCE_LIMIT_EXCEEDED",
            ),
            (
                upstream_api.BoundedRasterFailureCode.DEADLINE_EXCEEDED,
                "DEADLINE_EXCEEDED",
            ),
            (
                upstream_api.BoundedRasterFailureCode.INTERNAL_FAILURE,
                "INTERNAL_FAILURE",
            ),
        ]

        for code, expected in mappings:
            with self.subTest(
                code=code
            ):
                upstream = (
                    upstream_api.BoundedRasterResult(
                        outcome=(
                            upstream_api.BoundedRasterOutcome.FAILURE
                        ),
                        descriptor=None,
                        profile=None,
                        raster=None,
                        failure_code=code,
                    )
                )

                with patch.object(
                    self.runtime._bounded,
                    "observe",
                    return_value=upstream,
                ):
                    self.failure(
                        self.run_live(),
                        expected,
                    )

    def test_upstream_descriptor_must_match_snapshot(self):
        other_data = rgba_png(
            1,
            1,
            bytes([
                200,
                100,
                50,
                255,
            ]),
        )

        other_source, other_snapshot = capture(
            other_data
        )

        try:
            upstream = (
                upstream_api.BoundedRasterSamplingRuntime()
                .observe(
                    other_source,
                    other_snapshot,
                )
            )

            self.assertIs(
                upstream.outcome,
                upstream_api.BoundedRasterOutcome.SUCCESS,
            )

            with patch.object(
                self.runtime._bounded,
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
            self.runtime._bounded.observe
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
            self.runtime._bounded,
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
            api.RasterFeatureOutcome.SUCCESS,
        )

        self.assertIs(
            self.run_live().outcome,
            api.RasterFeatureOutcome.SUCCESS,
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
            api.RasterFeatureOutcome.SUCCESS,
        )

    def test_exception_mapping_and_recovery(self):
        with patch.object(
            module,
            "_extract",
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
            "_extract",
            side_effect=MemoryError(),
        ):
            self.failure(
                self.run_live(),
                "RESOURCE_LIMIT_EXCEEDED",
            )

        self.assertIs(
            self.run_live().outcome,
            api.RasterFeatureOutcome.SUCCESS,
        )

    def test_feature_failure_mapping_and_recovery(self):
        with patch.object(
            module,
            "_extract",
            side_effect=module._FeatureFailure(
                api.RasterFeatureFailureCode.FEATURE_INVALID
            ),
        ):
            self.failure(
                self.run_live(),
                "FEATURE_INVALID",
            )

        self.assertIs(
            self.run_live().outcome,
            api.RasterFeatureOutcome.SUCCESS,
        )

    def test_invalid_upstream_report_is_internal(self):
        with patch.object(
            self.runtime._bounded,
            "observe",
            return_value=Hostile(),
        ):
            self.failure(
                self.run_live(),
                "INTERNAL_FAILURE",
            )

        self.assertIs(
            self.run_live().outcome,
            api.RasterFeatureOutcome.SUCCESS,
        )

    def test_baseexception_not_swallowed(self):
        with patch.object(
            module,
            "_extract",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.run_live()

        self.assertIs(
            self.run_live().outcome,
            api.RasterFeatureOutcome.SUCCESS,
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
                    api.RasterFeatureObservationRuntime.observe
                ).parameters
            ),
            (
                "self",
                "runtime",
                "snapshot",
            ),
        )

        self.assertIn(
            "RasterFeatureObservationRuntime",
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