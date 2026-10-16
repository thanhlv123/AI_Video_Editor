import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from creator_studio.automation_runner import (
    AutomationPipelineCoordinator,
    AutomationRunStatus,
)
from creator_studio.automation_workflow import (
    AutomationStageStatus,
)
from creator_studio.render_backend import (
    RenderBackendCancelled,
    RenderBackendResult,
)


class SuccessfulBackend:
    def __init__(self):
        self.requests = []

    def render(
        self,
        request,
        *,
        progress_callback=None,
        cancel_token=None,
    ):
        self.requests.append(
            request
        )

        if cancel_token is not None:
            cancel_token.check()

        if progress_callback is not None:
            from creator_studio.render_backend import (
                RenderProgress,
            )

            progress_callback(
                RenderProgress(
                    phase="rendering",
                    percent=50.0,
                    detail="Synthetic M114 render.",
                )
            )

        request.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        request.output_path.write_bytes(
            b"m114-automation-video"
        )

        return RenderBackendResult(
            success=True,
            output_path=request.output_path,
            video_clips=2,
            has_narration=True,
            has_music=False,
            width=1920,
            height=1080,
            fps=30.0,
            raw={
                "success": True,
            },
        )


class FailingBackend:
    def render(
        self,
        request,
        *,
        progress_callback=None,
        cancel_token=None,
    ):
        raise RuntimeError(
            "Synthetic M114 backend failure."
        )


class CancelledBackend:
    def render(
        self,
        request,
        *,
        progress_callback=None,
        cancel_token=None,
    ):
        raise RenderBackendCancelled(
            "Synthetic M114 cancellation."
        )


class AutomationRunnerM114Tests(unittest.TestCase):

    def _touch(
        self,
        path,
        payload=b"x",
    ):
        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_bytes(
            payload
        )

        return path


    def _write_json(
        self,
        path,
        data,
    ):
        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path


    def _build_coordinator(
        self,
        directory,
    ):
        root = Path(
            directory
        )

        coordinator = (
            AutomationPipelineCoordinator.create(
                root,
                script_text="M114 automation test",
                language="en",
                config={},
            )
        )

        voice_relative = (
            "assets/voice/generated/"
            "voice_main.wav"
        )

        video_one_relative = (
            "assets/videos/downloaded/"
            "video_one.mp4"
        )

        video_two_relative = (
            "assets/videos/downloaded/"
            "video_two.mp4"
        )

        self._touch(
            root / voice_relative
        )

        self._touch(
            root / video_one_relative
        )

        self._touch(
            root / video_two_relative
        )

        manifest = {
            "format": (
                "creator_studio."
                "automatic_timeline.v1"
            ),
            "status": "ready",
            "duration_seconds": 10.6,
            "summary": {
                "scene_count": 2,
                "visual_clip_count": 2,
                "gap_fill_count": 0,
                "music_included": False,
                "unresolved_count": 0,
            },
            "source": {},
            "tracks": {
                "narration": {
                    "asset_id": "voice_main",
                    "path": voice_relative,
                    "start_seconds": 0.0,
                    "end_seconds": 10.6,
                    "timeline_duration_seconds": 10.6,
                    "source_duration_seconds": 10.6,
                    "gain_db": 0.0,
                    "primary": True,
                    "time_stretch": False,
                },
                "visuals": [
                    {
                        "clip_id": "visual_0001",
                        "kind": "scene",
                        "scene_id": "scene_001",
                        "start_seconds": 0.0,
                        "end_seconds": 6.4,
                        "duration_seconds": 6.4,
                        "asset": {
                            "asset_id": "video_one",
                            "media_type": "video",
                            "path": video_one_relative,
                            "duration_seconds": 20.0,
                            "width": 1920,
                            "height": 1080,
                            "origin": "downloaded",
                        },
                        "operation": {
                            "mode": "trim",
                            "source_in_seconds": 0.0,
                            "source_out_seconds": 6.4,
                            "playback_rate": 1.0,
                            "loop": False,
                            "speed_change": False,
                        },
                    },
                    {
                        "clip_id": "visual_0002",
                        "kind": "scene",
                        "scene_id": "scene_002",
                        "start_seconds": 6.4,
                        "end_seconds": 10.6,
                        "duration_seconds": 4.2,
                        "asset": {
                            "asset_id": "video_two",
                            "media_type": "video",
                            "path": video_two_relative,
                            "duration_seconds": 20.0,
                            "width": 1920,
                            "height": 1080,
                            "origin": "downloaded",
                        },
                        "operation": {
                            "mode": "trim",
                            "source_in_seconds": 0.0,
                            "source_out_seconds": 4.2,
                            "playback_rate": 1.0,
                            "loop": False,
                            "speed_change": False,
                        },
                    },
                ],
                "music": None,
            },
            "music_state": {
                "status": "not_selected",
                "included": False,
            },
            "policy": {},
            "issues": [],
        }

        manifest_path = (
            coordinator.run_dir
            / "timeline_manifest.json"
        )

        self._write_json(
            manifest_path,
            manifest,
        )

        coordinator.timeline_assembly_completed(
            status="ready",
            scene_count=2,
            visual_clip_count=2,
            gap_fill_count=0,
            duration_seconds=10.6,
            music_included=False,
            manifest_filename=(
                "timeline_manifest.json"
            ),
        )

        return (
            coordinator,
            manifest_path,
        )


    def test_run_render_export_completes_render_and_export_stages(self):
        backend = SuccessfulBackend()

        progress = []

        with TemporaryDirectory() as directory:

            coordinator, manifest_path = (
                self._build_coordinator(
                    directory
                )
            )

            result = (
                coordinator.run_render_export(
                    timeline_manifest_path=(
                        manifest_path
                    ),
                    backend=backend,
                    progress_callback=(
                        progress.append
                    ),
                )
            )

            saved = json.loads(
                coordinator.state_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertTrue(
                result.output_path.is_file()
            )

            self.assertTrue(
                result.manifest_path.is_file()
            )

        self.assertEqual(
            coordinator.status,
            AutomationRunStatus.COMPLETED,
        )

        self.assertEqual(
            coordinator.state.stage_status(
                "render"
            ),
            AutomationStageStatus.COMPLETED,
        )

        self.assertEqual(
            coordinator.state.stage_status(
                "export"
            ),
            AutomationStageStatus.COMPLETED,
        )

        self.assertEqual(
            len(backend.requests),
            1,
        )

        self.assertEqual(
            result.duration_seconds,
            10.6,
        )

        self.assertEqual(
            coordinator.render_export[
                "status"
            ],
            "completed",
        )

        self.assertEqual(
            saved["render_export"][
                "status"
            ],
            "completed",
        )

        self.assertTrue(
            saved["render_export"][
                "output_path"
            ].endswith(
                "final_video_001.mp4"
            )
        )

        self.assertTrue(
            progress
        )


    def test_preflight_blocks_missing_visual_before_backend_or_output(self):
        with TemporaryDirectory() as directory:
            coordinator, manifest_path = self._build_coordinator(directory)
            missing_visual = (
                Path(directory)
                / "assets/videos/downloaded/video_one.mp4"
            )
            missing_visual.unlink()
            backend = SuccessfulBackend()

            with self.assertRaisesRegex(Exception, r"visual\\[0\\]"):
                coordinator.run_render_export(
                    timeline_manifest_path=manifest_path,
                    backend=backend,
                )

            self.assertEqual(backend.requests, [])
            self.assertEqual(coordinator.status, AutomationRunStatus.FAILED)
            self.assertEqual(
                coordinator.state.stage_status("render"),
                AutomationStageStatus.FAILED,
            )
            self.assertIn("missing_media", coordinator.error)
            self.assertFalse(
                (coordinator.run_dir / "render_export_manifest.json").exists()
            )

    def test_run_render_export_failure_marks_render_failed(self):
        with TemporaryDirectory() as directory:

            coordinator, manifest_path = (
                self._build_coordinator(
                    directory
                )
            )

            with self.assertRaises(
                Exception
            ):
                coordinator.run_render_export(
                    timeline_manifest_path=(
                        manifest_path
                    ),
                    backend=FailingBackend(),
                )

            saved = json.loads(
                coordinator.state_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            coordinator.status,
            AutomationRunStatus.FAILED,
        )

        self.assertEqual(
            coordinator.state.stage_status(
                "render"
            ),
            AutomationStageStatus.FAILED,
        )

        self.assertEqual(
            coordinator.render_export[
                "status"
            ],
            "failed",
        )

        self.assertEqual(
            saved["render_export"][
                "status"
            ],
            "failed",
        )


    def test_run_render_export_cancellation_marks_run_cancelled(self):
        with TemporaryDirectory() as directory:

            coordinator, manifest_path = (
                self._build_coordinator(
                    directory
                )
            )

            with self.assertRaises(
                RenderBackendCancelled
            ):
                coordinator.run_render_export(
                    timeline_manifest_path=(
                        manifest_path
                    ),
                    backend=CancelledBackend(),
                )

            saved = json.loads(
                coordinator.state_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            coordinator.status,
            AutomationRunStatus.CANCELLED,
        )

        self.assertEqual(
            coordinator.state.stage_status(
                "render"
            ),
            AutomationStageStatus.CANCELLED,
        )

        self.assertEqual(
            coordinator.render_export[
                "status"
            ],
            "cancelled",
        )

        self.assertEqual(
            saved["render_export"][
                "status"
            ],
            "cancelled",
        )


if __name__ == "__main__":
    unittest.main()