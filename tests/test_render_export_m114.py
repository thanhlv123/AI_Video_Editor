import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from creator_studio.render_backend import (
    RenderBackendCancelled,
    RenderBackendResult,
)
from creator_studio.render_export import (
    RenderExportError,
    RenderExportService,
)


class CapturingBackend:
    def __init__(
        self,
        *,
        fail=False,
        cancel=False,
    ):
        self.requests = []
        self.fail = fail
        self.cancel = cancel

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

        if self.cancel:
            raise RenderBackendCancelled(
                "Synthetic render cancelled."
            )

        if self.fail:
            raise RuntimeError(
                "Synthetic render failure."
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
                    detail="Synthetic render.",
                )
            )

        request.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        request.output_path.write_bytes(
            b"synthetic-m114-video"
        )

        return RenderBackendResult(
            success=True,
            output_path=request.output_path,
            video_clips=2,
            has_narration=True,
            has_music=(
                request.music_track_id
                is not None
            ),
            width=(
                request.project.settings.width
            ),
            height=(
                request.project.settings.height
            ),
            fps=(
                request.project.settings.fps
            ),
            raw={
                "success": True,
            },
        )


class RenderExportM114Tests(unittest.TestCase):

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


    def _build_fixture(
        self,
        directory,
        *,
        status="ready",
        include_music=True,
    ):
        root = Path(
            directory
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

        music_relative = (
            "assets/music/imported/"
            "calm_cinematic.mp3"
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

        self._touch(
            root / music_relative
        )


        manifest = {
            "format": (
                "creator_studio."
                "automatic_timeline.v1"
            ),
            "created_at": (
                "2026-10-16T08:25:26+00:00"
            ),
            "status": status,
            "duration_seconds": 10.6,
            "summary": {
                "scene_count": 2,
                "visual_clip_count": 2,
                "gap_fill_count": 0,
                "music_included": (
                    include_music
                ),
                "unresolved_count": 0,
            },
            "source": {
                "voice_scenes": (
                    "work/voice/"
                    "voice_test/"
                    "voice_scenes.json"
                ),
                "final_renderable": (
                    "final_renderable_assets.json"
                ),
                "music_selection": (
                    "music_selection_manifest.json"
                ),
            },
            "tracks": {
                "narration": {
                    "asset_id": (
                        "voice_test"
                    ),
                    "path": (
                        voice_relative
                    ),
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
                        "clip_id": (
                            "visual_0001"
                        ),
                        "kind": "scene",
                        "scene_id": (
                            "scene_001"
                        ),
                        "start_seconds": 0.0,
                        "end_seconds": 6.4,
                        "duration_seconds": 6.4,
                        "asset": {
                            "asset_id": (
                                "video_one"
                            ),
                            "media_type": (
                                "video"
                            ),
                            "path": (
                                video_one_relative
                            ),
                            "duration_seconds": (
                                27.8278
                            ),
                            "width": 1920,
                            "height": 1080,
                            "origin": (
                                "downloaded"
                            ),
                        },
                        "operation": {
                            "mode": "trim",
                            "source_in_seconds": 0.0,
                            "source_out_seconds": 6.4,
                            "playback_rate": 1.0,
                            "loop": False,
                            "speed_change": False,
                        },
                        "fit": {
                            "mode": "cover",
                            "position": "center",
                        },
                    },
                    {
                        "clip_id": (
                            "visual_0002"
                        ),
                        "kind": "scene",
                        "scene_id": (
                            "scene_002"
                        ),
                        "start_seconds": 6.4,
                        "end_seconds": 10.6,
                        "duration_seconds": 4.2,
                        "asset": {
                            "asset_id": (
                                "video_two"
                            ),
                            "media_type": (
                                "video"
                            ),
                            "path": (
                                video_two_relative
                            ),
                            "duration_seconds": (
                                14.356667
                            ),
                            "width": 2048,
                            "height": 1080,
                            "origin": (
                                "downloaded"
                            ),
                        },
                        "operation": {
                            "mode": "trim",
                            "source_in_seconds": 0.0,
                            "source_out_seconds": 4.2,
                            "playback_rate": 1.0,
                            "loop": False,
                            "speed_change": False,
                        },
                        "fit": {
                            "mode": "cover",
                            "position": "center",
                        },
                    },
                ],
                "music": {
                    "path": (
                        music_relative
                    ),
                    "start_seconds": 0.0,
                    "end_seconds": 10.6,
                    "target_duration_seconds": 10.6,
                    "source_duration_seconds": (
                        136.615397
                    ),
                    "operation": {
                        "loop_required": False,
                        "trim_to_target": True,
                        "playback_rate": 1.0,
                    },
                    "mix": {
                        "gain_db": -24.0,
                        "fade_in_seconds": 1.5,
                        "fade_out_seconds": 2.0,
                        "ducking_enabled": True,
                        "ducking_reduction_db": 6.0,
                        "voice_is_primary": True,
                    },
                },
            },
            "music_state": {
                "status": (
                    "selected"
                    if include_music
                    else "not_selected"
                ),
                "included": (
                    include_music
                ),
            },
            "policy": {},
            "issues": [],
        }


        manifest_path = (
            root
            / "work"
            / "automation"
            / "run_test"
            / "timeline_manifest.json"
        )

        self._write_json(
            manifest_path,
            manifest,
        )


        voice_scenes_path = (
            root
            / "work"
            / "voice"
            / "voice_test"
            / "voice_scenes.json"
        )

        self._write_json(
            voice_scenes_path,
            {
                "status": "completed",
            },
        )


        return (
            root,
            manifest_path,
            manifest,
        )


    def test_ready_manifest_builds_core_project_and_exports(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        progress = []

        with TemporaryDirectory() as directory:

            root, manifest_path, _ = (
                self._build_fixture(
                    directory
                )
            )

            result = service.export(
                timeline_manifest_path=(
                    manifest_path
                ),
                project_root=root,
                progress_callback=(
                    progress.append
                ),
            )


            self.assertTrue(
                result.output_path.is_file()
            )

            self.assertTrue(
                result.manifest_path.is_file()
            )


            saved = json.loads(
                result.manifest_path.read_text(
                    encoding="utf-8"
                )
            )


        self.assertEqual(
            result.status,
            "completed",
        )

        self.assertEqual(
            result.duration_seconds,
            10.6,
        )

        self.assertEqual(
            result.width,
            1920,
        )

        self.assertEqual(
            result.height,
            1080,
        )

        self.assertEqual(
            result.fps,
            30.0,
        )


        self.assertEqual(
            len(backend.requests),
            1,
        )

        request = backend.requests[0]

        project = request.project


        self.assertEqual(
            request.video_track_id,
            "video_1",
        )

        self.assertEqual(
            request.narration_track_id,
            "voice_1",
        )

        self.assertEqual(
            request.music_track_id,
            "music_1",
        )

        self.assertFalse(
            request.allow_overwrite
        )


        video_track = (
            project.timeline.get_track(
                "video_1"
            )
        )

        voice_track = (
            project.timeline.get_track(
                "voice_1"
            )
        )

        music_track = (
            project.timeline.get_track(
                "music_1"
            )
        )


        self.assertIsNotNone(
            video_track
        )

        self.assertIsNotNone(
            voice_track
        )

        self.assertIsNotNone(
            music_track
        )

        self.assertEqual(
            len(video_track.clips),
            2,
        )

        self.assertEqual(
            len(voice_track.clips),
            1,
        )

        self.assertEqual(
            len(music_track.clips),
            1,
        )


        self.assertEqual(
            video_track.clips[0].start,
            0.0,
        )

        self.assertEqual(
            video_track.clips[0].duration,
            6.4,
        )

        self.assertEqual(
            video_track.clips[1].start,
            6.4,
        )

        self.assertEqual(
            video_track.clips[1].duration,
            4.2,
        )


        self.assertEqual(
            request.mix_policy.music_gain_db,
            -24.0,
        )

        self.assertEqual(
            request.mix_policy.music_fade_in_seconds,
            1.5,
        )

        self.assertEqual(
            request.mix_policy.music_fade_out_seconds,
            2.0,
        )

        self.assertTrue(
            request.mix_policy.ducking_enabled
        )

        self.assertEqual(
            request.mix_policy.ducking_reduction_db,
            6.0,
        )

        self.assertTrue(
            request.mix_policy.voice_is_primary
        )


        self.assertEqual(
            saved["format"],
            (
                "creator_studio."
                "render_export.v1"
            ),
        )

        self.assertEqual(
            saved["status"],
            "completed",
        )

        self.assertEqual(
            saved["duration_seconds"],
            10.6,
        )

        self.assertEqual(
            saved["summary"][
                "visual_clip_count"
            ],
            2,
        )

        self.assertTrue(
            saved["summary"][
                "narration_included"
            ]
        )

        self.assertTrue(
            saved["summary"][
                "music_included"
            ]
        )


        phases = [
            event.phase
            for event in progress
        ]

        self.assertEqual(
            phases,
            [
                "validating",
                "prepared",
                "rendering",
            ],
        )


    def test_asset_paths_are_resolved_from_project_root(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, manifest = (
                self._build_fixture(
                    directory
                )
            )

            service.export(
                manifest_path,
                root,
            )

            request = backend.requests[0]

            project = request.project

            media = project.get_media(
                "video_one"
            )

            expected = (
                root
                / manifest["tracks"][
                    "visuals"
                ][0]["asset"]["path"]
            ).resolve()


        self.assertEqual(
            Path(media.path),
            expected,
        )

        self.assertTrue(
            Path(media.path).is_absolute()
        )


    def test_export_names_never_overwrite_existing_output(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, _ = (
                self._build_fixture(
                    directory
                )
            )

            first = service.export(
                manifest_path,
                root,
            )

            second = service.export(
                manifest_path,
                root,
            )


            self.assertTrue(
                first.output_path.exists()
            )

            self.assertTrue(
                second.output_path.exists()
            )


        self.assertEqual(
            first.output_path.name,
            "final_video_001.mp4",
        )

        self.assertEqual(
            second.output_path.name,
            "final_video_002.mp4",
        )

        self.assertNotEqual(
            first.output_path,
            second.output_path,
        )

        self.assertEqual(
            first.manifest_path.name,
            "render_export_manifest.json",
        )

        self.assertEqual(
            second.manifest_path.name,
            "render_export_manifest_002.json",
        )


    def test_missing_visual_asset_fails_before_backend(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, manifest = (
                self._build_fixture(
                    directory
                )
            )

            missing = (
                root
                / manifest["tracks"][
                    "visuals"
                ][0]["asset"]["path"]
            )

            missing.unlink()


            with self.assertRaises(
                RenderExportError
            ) as raised:

                service.export(
                    manifest_path,
                    root,
                )


        self.assertIn(
            "file does not exist",
            str(raised.exception),
        )

        self.assertEqual(
            backend.requests,
            [],
        )


    def test_missing_narration_fails_before_backend(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, manifest = (
                self._build_fixture(
                    directory
                )
            )

            narration_path = (
                root
                / manifest["tracks"][
                    "narration"
                ]["path"]
            )

            narration_path.unlink()


            with self.assertRaises(
                RenderExportError
            ):

                service.export(
                    manifest_path,
                    root,
                )


        self.assertEqual(
            backend.requests,
            [],
        )


    def test_non_ready_manifest_is_rejected(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, _ = (
                self._build_fixture(
                    directory,
                    status="blocked",
                )
            )


            with self.assertRaises(
                RenderExportError
            ) as raised:

                service.export(
                    manifest_path,
                    root,
                )


        self.assertIn(
            "not ready",
            str(raised.exception),
        )

        self.assertEqual(
            backend.requests,
            [],
        )


    def test_music_can_be_excluded(self):
        backend = CapturingBackend()

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, _ = (
                self._build_fixture(
                    directory,
                    include_music=False,
                )
            )

            result = service.export(
                manifest_path,
                root,
            )

            request = backend.requests[0]

            saved = json.loads(
                result.manifest_path.read_text(
                    encoding="utf-8"
                )
            )


        self.assertIsNone(
            request.music_track_id
        )

        self.assertIsNone(
            request.project.timeline.get_track(
                "music_1"
            )
        )

        self.assertFalse(
            saved["summary"][
                "music_included"
            ]
        )


    def test_backend_failure_writes_failed_manifest(self):
        backend = CapturingBackend(
            fail=True
        )

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, _ = (
                self._build_fixture(
                    directory
                )
            )


            with self.assertRaises(
                RenderExportError
            ):

                service.export(
                    manifest_path,
                    root,
                )


            export_manifest_path = (
                manifest_path.parent
                / "render_export_manifest.json"
            )

            self.assertTrue(
                export_manifest_path.exists()
            )

            saved = json.loads(
                export_manifest_path.read_text(
                    encoding="utf-8"
                )
            )


        self.assertEqual(
            saved["status"],
            "failed",
        )

        self.assertEqual(
            saved["issues"],
            [
                "render_failed"
            ],
        )

        self.assertIn(
            "Synthetic render failure",
            saved["error"],
        )


    def test_backend_cancellation_writes_cancelled_manifest(self):
        backend = CapturingBackend(
            cancel=True
        )

        service = RenderExportService(
            backend=backend
        )

        with TemporaryDirectory() as directory:

            root, manifest_path, _ = (
                self._build_fixture(
                    directory
                )
            )


            with self.assertRaises(
                RenderBackendCancelled
            ):

                service.export(
                    manifest_path,
                    root,
                )


            export_manifest_path = (
                manifest_path.parent
                / "render_export_manifest.json"
            )

            saved = json.loads(
                export_manifest_path.read_text(
                    encoding="utf-8"
                )
            )


        self.assertEqual(
            saved["status"],
            "cancelled",
        )

        self.assertEqual(
            saved["issues"],
            [
                "render_cancelled"
            ],
        )


    def test_null_narration_source_duration_uses_timeline_fallback(self):
        backend = CapturingBackend()
        service = RenderExportService(backend=backend)
        with TemporaryDirectory() as directory:
            root, manifest_path, manifest = self._build_fixture(
                directory, include_music=False
            )
            manifest["tracks"]["narration"]["source_duration_seconds"] = None
            self._write_json(manifest_path, manifest)
            result = service.export(manifest_path, root)
            self.assertTrue(result.output_path.is_file())
            self.assertEqual(len(backend.requests), 1)
            request = backend.requests[0]
            self.assertIsNone(request.music_track_id)
            self.assertEqual(
                request.project.get_media("voice_test").duration,
                manifest["duration_seconds"],
            )

    def test_absent_narration_source_duration_uses_timeline_fallback(self):
        backend = CapturingBackend()
        service = RenderExportService(backend=backend)
        with TemporaryDirectory() as directory:
            root, manifest_path, manifest = self._build_fixture(directory)
            manifest["tracks"]["narration"].pop("source_duration_seconds")
            self._write_json(manifest_path, manifest)
            service.export(manifest_path, root)
            self.assertEqual(
                backend.requests[0].project.get_media("voice_test").duration,
                10.6,
            )

    def test_known_narration_source_duration_is_preserved(self):
        backend = CapturingBackend()
        service = RenderExportService(backend=backend)
        with TemporaryDirectory() as directory:
            root, manifest_path, manifest = self._build_fixture(directory)
            manifest["tracks"]["narration"]["source_duration_seconds"] = 12.5
            self._write_json(manifest_path, manifest)
            service.export(manifest_path, root)
            self.assertEqual(
                backend.requests[0].project.get_media("voice_test").duration,
                12.5,
            )

    def test_invalid_nonnull_narration_duration_fails_before_backend(self):
        backend = CapturingBackend()
        service = RenderExportService(backend=backend)
        with TemporaryDirectory() as directory:
            root, manifest_path, manifest = self._build_fixture(directory)
            for value in (0, -1, False, "", "nan", "inf"):
                with self.subTest(value=value):
                    manifest["tracks"]["narration"]["source_duration_seconds"] = value
                    self._write_json(manifest_path, manifest)
                    with self.assertRaises(RenderExportError):
                        service.export(manifest_path, root)
                    self.assertEqual(backend.requests, [])

    def test_null_narration_duration_does_not_overwrite_existing_export(self):
        backend = CapturingBackend()
        service = RenderExportService(backend=backend)
        with TemporaryDirectory() as directory:
            root, manifest_path, manifest = self._build_fixture(directory)
            manifest["tracks"]["narration"]["source_duration_seconds"] = None
            self._write_json(manifest_path, manifest)
            first = service.export(manifest_path, root)
            first_bytes = first.output_path.read_bytes()
            second = service.export(manifest_path, root)
            self.assertNotEqual(first.output_path, second.output_path)
            self.assertEqual(first.output_path.read_bytes(), first_bytes)
            self.assertTrue(second.output_path.is_file())
            self.assertEqual(len(backend.requests), 2)


if __name__ == "__main__":
    unittest.main()