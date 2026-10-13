"""M85 authority-bound semantic vision observation runtime."""

import ast
import inspect
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch

import creator_studio.bounded_raster_sampling as raster_api
import creator_studio.semantic_vision_observer as api
import creator_studio.semantic_vision_observer.runtime as module
import creator_studio.visual_evidence_observer as evidence_api

from creator_studio.source_snapshot import (
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
)
from tests.test_png8_structural_preflight import (
    capture,
    png,
)
from tests.test_raster_feature_runtime import (
    rgba_png,
)


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")

    def __repr__(self):
        raise AssertionError("hostile repr")

    def __eq__(self, other):
        raise AssertionError("hostile equality")


def adapter_response():
    return api.SemanticVisionAdapterResponse(
        schema_version=(
            api.SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ),
        scene_setting=(
            api.SceneSetting.INDOOR
        ),
        shot_scale=(
            api.ShotScale.MEDIUM
        ),
        visual_mood=(
            api.VisualMood.CALM
        ),
        subjects=(
            api.SemanticLabel(
                "person",
                950,
            ),
            api.SemanticLabel(
                "wooden table",
                700,
            ),
        ),
        activities=(
            api.SemanticLabel(
                "cooking",
                900,
            ),
        ),
        scene_tags=(
            api.SemanticLabel(
                "rural kitchen",
                850,
            ),
        ),
        confidence_milli=900,
    )


class ValidProvider(
    api.SemanticVisionProvider
):
    def __init__(self):
        self.requests = []

    def observe(self, request, check):
        self.requests.append(
            request
        )

        check()

        return adapter_response()


class FailureProvider(
    api.SemanticVisionProvider
):
    def __init__(self, code):
        self.code = code

    def observe(self, request, check):
        raise api.SemanticVisionProviderFailure(
            self.code
        )


class InterruptProvider(
    api.SemanticVisionProvider
):
    def observe(self, request, check):
        raise KeyboardInterrupt()


class SemanticVisionRuntimeTests(
    unittest.TestCase
):

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

        self.provider = ValidProvider()

        self.runtime = (
            api.SemanticVisionObservationRuntime(
                self.provider
            )
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
            api.SemanticVisionOutcome.FAILURE,
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
            result.observation
        )

        api.validate_semantic_vision_result(
            result
        )

    def test_success(self):
        result = self.run_live()

        self.assertIs(
            result.outcome,
            api.SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            result.descriptor,
            self.snapshot.descriptor,
        )

        self.assertEqual(
            result.observation.schema_version,
            1,
        )

        self.assertIs(
            result.observation.method,
            api.SemanticVisionMethod
            .STRUCTURED_VISION_V1,
        )

        self.assertIs(
            result.observation.scene_setting,
            api.SceneSetting.INDOOR,
        )

        self.assertIs(
            result.observation.shot_scale,
            api.ShotScale.MEDIUM,
        )

        self.assertIs(
            result.observation.visual_mood,
            api.VisualMood.CALM,
        )

        self.assertEqual(
            result.observation.subjects[0].label,
            "person",
        )

        self.assertEqual(
            result.observation.activities[0].label,
            "cooking",
        )

        self.assertEqual(
            result.observation.confidence_milli,
            900,
        )

        api.validate_semantic_vision_result(
            result
        )

    def test_provider_receives_coherent_request(self):
        result = self.run_live()

        self.assertIs(
            result.outcome,
            api.SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            len(self.provider.requests),
            1,
        )

        request = self.provider.requests[0]

        self.assertIs(
            type(request),
            api.SemanticVisionAdapterRequest,
        )

        api.validate_semantic_vision_adapter_request(
            request
        )

        self.assertEqual(
            request.raster.source_width,
            request.evidence.features.source_width,
        )

        self.assertEqual(
            request.raster.source_height,
            request.evidence.features.source_height,
        )

        self.assertEqual(
            request.raster.width,
            request.evidence.features.width,
        )

        self.assertEqual(
            request.raster.height,
            request.evidence.features.height,
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

        source.release(
            snapshot
        )

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
                        "UPSTREAM_EVIDENCE_FAILED",
                    )

                finally:
                    source.release(
                        snapshot
                    )

    def test_all_evidence_failure_mapping(self):
        mappings = [
            (
                evidence_api.VisualEvidenceFailureCode
                .SNAPSHOT_AUTHORITY_INVALID,
                "SNAPSHOT_AUTHORITY_INVALID",
            ),
            (
                evidence_api.VisualEvidenceFailureCode
                .UPSTREAM_FEATURE_FAILED,
                "UPSTREAM_EVIDENCE_FAILED",
            ),
            (
                evidence_api.VisualEvidenceFailureCode
                .EVIDENCE_INVALID,
                "UPSTREAM_EVIDENCE_FAILED",
            ),
            (
                evidence_api.VisualEvidenceFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                "RESOURCE_LIMIT_EXCEEDED",
            ),
            (
                evidence_api.VisualEvidenceFailureCode
                .DEADLINE_EXCEEDED,
                "DEADLINE_EXCEEDED",
            ),
            (
                evidence_api.VisualEvidenceFailureCode
                .INTERNAL_FAILURE,
                "INTERNAL_FAILURE",
            ),
        ]

        for code, expected in mappings:
            upstream = evidence_api.VisualEvidenceResult(
                outcome=(
                    evidence_api.VisualEvidenceOutcome.FAILURE
                ),
                descriptor=None,
                profile=None,
                evidence=None,
                failure_code=code,
            )

            with self.subTest(
                code=code
            ):
                with patch.object(
                    self.runtime._evidence,
                    "observe",
                    return_value=upstream,
                ):
                    self.failure(
                        self.run_live(),
                        expected,
                    )

    def test_all_raster_failure_mapping(self):
        mappings = [
            (
                raster_api.BoundedRasterFailureCode
                .SNAPSHOT_AUTHORITY_INVALID,
                "SNAPSHOT_AUTHORITY_INVALID",
            ),
            (
                raster_api.BoundedRasterFailureCode
                .UPSTREAM_RASTER_FAILED,
                "UPSTREAM_EVIDENCE_FAILED",
            ),
            (
                raster_api.BoundedRasterFailureCode
                .SAMPLING_INVALID,
                "UPSTREAM_EVIDENCE_FAILED",
            ),
            (
                raster_api.BoundedRasterFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                "RESOURCE_LIMIT_EXCEEDED",
            ),
            (
                raster_api.BoundedRasterFailureCode
                .DEADLINE_EXCEEDED,
                "DEADLINE_EXCEEDED",
            ),
            (
                raster_api.BoundedRasterFailureCode
                .INTERNAL_FAILURE,
                "INTERNAL_FAILURE",
            ),
        ]

        for code, expected in mappings:
            upstream = raster_api.BoundedRasterResult(
                outcome=(
                    raster_api.BoundedRasterOutcome.FAILURE
                ),
                descriptor=None,
                profile=None,
                raster=None,
                failure_code=code,
            )

            with self.subTest(
                code=code
            ):
                with patch.object(
                    self.runtime._raster,
                    "observe",
                    return_value=upstream,
                ):
                    self.failure(
                        self.run_live(),
                        expected,
                    )

    def test_evidence_descriptor_must_match(self):
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
                evidence_api.VisualEvidenceObservationRuntime()
                .observe(
                    other_source,
                    other_snapshot,
                )
            )

            self.assertIs(
                upstream.outcome,
                evidence_api.VisualEvidenceOutcome.SUCCESS,
            )

            with patch.object(
                self.runtime._evidence,
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

    def test_raster_descriptor_must_match(self):
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
                raster_api.BoundedRasterSamplingRuntime()
                .observe(
                    other_source,
                    other_snapshot,
                )
            )

            self.assertIs(
                upstream.outcome,
                raster_api.BoundedRasterOutcome.SUCCESS,
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

    def test_provider_failure_mapping(self):
        mappings = [
            (
                api.SemanticVisionProviderFailureCode.UNAVAILABLE,
                "ADAPTER_UNAVAILABLE",
            ),
            (
                api.SemanticVisionProviderFailureCode.RESPONSE_INVALID,
                "RESPONSE_INVALID",
            ),
            (
                api.SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                "RESOURCE_LIMIT_EXCEEDED",
            ),
            (
                api.SemanticVisionProviderFailureCode.DEADLINE_EXCEEDED,
                "DEADLINE_EXCEEDED",
            ),
            (
                api.SemanticVisionProviderFailureCode.INTERNAL_FAILURE,
                "INTERNAL_FAILURE",
            ),
        ]

        for code, expected in mappings:
            with self.subTest(
                code=code
            ):
                runtime = (
                    api.SemanticVisionObservationRuntime(
                        FailureProvider(
                            code
                        )
                    )
                )

                self.failure(
                    runtime.observe(
                        self.source,
                        self.snapshot,
                    ),
                    expected,
                )

    def test_invalid_provider_is_adapter_unavailable(self):
        runtime = (
            api.SemanticVisionObservationRuntime(
                object()
            )
        )

        self.failure(
            runtime.observe(
                self.source,
                self.snapshot,
            ),
            "ADAPTER_UNAVAILABLE",
        )

    def test_concurrent_gate(self):
        entered = Event()
        finish = Event()
        results = []

        original = (
            self.runtime._evidence.observe
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
            self.runtime._evidence,
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
            api.SemanticVisionOutcome.SUCCESS,
        )

        self.assertIs(
            self.run_live().outcome,
            api.SemanticVisionOutcome.SUCCESS,
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
            api.SemanticVisionOutcome.SUCCESS,
        )

    def test_exception_mapping_and_recovery(self):
        with patch.object(
            module,
            "_build_semantic_observation",
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
            "_build_semantic_observation",
            side_effect=MemoryError(),
        ):
            self.failure(
                self.run_live(),
                "RESOURCE_LIMIT_EXCEEDED",
            )

        self.assertIs(
            self.run_live().outcome,
            api.SemanticVisionOutcome.SUCCESS,
        )

    def test_invalid_upstream_report_is_internal(self):
        with patch.object(
            self.runtime._evidence,
            "observe",
            return_value=Hostile(),
        ):
            self.failure(
                self.run_live(),
                "INTERNAL_FAILURE",
            )

        self.assertIs(
            self.run_live().outcome,
            api.SemanticVisionOutcome.SUCCESS,
        )

    def test_baseexception_not_swallowed(self):
        runtime = (
            api.SemanticVisionObservationRuntime(
                InterruptProvider()
            )
        )

        with self.assertRaises(
            KeyboardInterrupt
        ):
            runtime.observe(
                self.source,
                self.snapshot,
            )

        runtime._provider = ValidProvider()

        self.assertIs(
            runtime.observe(
                self.source,
                self.snapshot,
            ).outcome,
            api.SemanticVisionOutcome.SUCCESS,
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
                    api.SemanticVisionObservationRuntime.__init__
                ).parameters
            ),
            (
                "self",
                "provider",
            ),
        )

        self.assertEqual(
            tuple(
                inspect.signature(
                    api.SemanticVisionObservationRuntime.observe
                ).parameters
            ),
            (
                "self",
                "runtime",
                "snapshot",
            ),
        )

        self.assertIn(
            "SemanticVisionObservationRuntime",
            api.__all__,
        )

        self.assertIn(
            "SemanticVisionProvider",
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
            "httpx",
            "aiohttp",
            "openai",
            "anthropic",
            "google",
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