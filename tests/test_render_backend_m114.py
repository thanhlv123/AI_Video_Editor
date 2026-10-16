from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from creator_studio.render_backend import (
    RenderBackendCancelled,
    RenderBackendError,
    RenderBackendRequest,
    RenderCancellationToken,
    RenderMixPolicy,
    RenderProgress,
    TimelineRendererBackend,
)


class CompatibleRenderer:
    def __init__(self):
        self.calls = []

    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1",
        music_track_id=None,
        mix_policy=None,
        progress_callback=None,
        cancel_event=None,
    ):
        self.calls.append(
            {
                "project": project,
                "output_path": output_path,
                "video_track_id": video_track_id,
                "audio_track_id": audio_track_id,
                "music_track_id": music_track_id,
                "mix_policy": mix_policy,
                "cancel_event": cancel_event,
            }
        )

        if progress_callback is not None:
            progress_callback(
                "rendering",
                50.0,
                "Synthetic render in progress.",
            )

        Path(output_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        Path(output_path).write_bytes(
            b"synthetic-m114-video"
        )

        return {
            "success": True,
            "output": str(output_path),
            "video_clips": 2,
            "has_audio": True,
            "has_music": music_track_id is not None,
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
        }


class LegacyRenderer:
    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1",
    ):
        raise AssertionError(
            "Legacy renderer must not be called."
        )


class FailingRenderer:
    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1",
        music_track_id=None,
        mix_policy=None,
        progress_callback=None,
        cancel_event=None,
    ):
        raise RuntimeError(
            "synthetic ffmpeg failure"
        )


class MissingOutputRenderer:
    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1",
        music_track_id=None,
        mix_policy=None,
        progress_callback=None,
        cancel_event=None,
    ):
        return {
            "success": True,
            "output": str(output_path),
            "video_clips": 1,
        }


class FalseResultRenderer:
    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1",
        music_track_id=None,
        mix_policy=None,
        progress_callback=None,
        cancel_event=None,
    ):
        return {
            "success": False,
            "output": str(output_path),
        }


class RenderBackendM114Tests(unittest.TestCase):

    def test_progress_validation(self):
        progress = RenderProgress(
            phase="rendering",
            percent=42.5,
            detail="working",
        )

        self.assertEqual(
            progress.phase,
            "rendering",
        )

        self.assertEqual(
            progress.percent,
            42.5,
        )

        with self.assertRaises(ValueError):
            RenderProgress(
                phase="",
                percent=10,
            )

        with self.assertRaises(ValueError):
            RenderProgress(
                phase="rendering",
                percent=-1,
            )

        with self.assertRaises(ValueError):
            RenderProgress(
                phase="rendering",
                percent=101,
            )


    def test_mix_policy_validation_and_projection(self):
        policy = RenderMixPolicy(
            narration_gain_db=0.0,
            music_gain_db=-24.0,
            music_fade_in_seconds=1.5,
            music_fade_out_seconds=2.0,
            ducking_enabled=True,
            ducking_reduction_db=6.0,
            voice_is_primary=True,
        )

        projected = policy.to_renderer_options()

        self.assertEqual(
            projected["music_gain_db"],
            -24.0,
        )

        self.assertEqual(
            projected["ducking_reduction_db"],
            6.0,
        )

        self.assertTrue(
            projected["ducking_enabled"]
        )

        with self.assertRaises(ValueError):
            RenderMixPolicy(
                music_fade_in_seconds=-1,
            )

        with self.assertRaises(ValueError):
            RenderMixPolicy(
                ducking_reduction_db=-1,
            )


    def test_request_validation(self):
        request = RenderBackendRequest(
            project=object(),
            output_path="result.mp4",
            duration_seconds=10.6,
            music_track_id="music_1",
        )

        self.assertEqual(
            request.output_path,
            Path("result.mp4"),
        )

        self.assertEqual(
            request.duration_seconds,
            10.6,
        )

        with self.assertRaises(ValueError):
            RenderBackendRequest(
                project=None,
                output_path="result.mp4",
                duration_seconds=10.6,
            )

        with self.assertRaises(ValueError):
            RenderBackendRequest(
                project=object(),
                output_path="result.mp4",
                duration_seconds=0,
            )


    def test_legacy_renderer_is_rejected_before_execution(self):
        backend = TimelineRendererBackend(
            renderer=LegacyRenderer()
        )

        with TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "legacy.mp4"
            )

            request = RenderBackendRequest(
                project=object(),
                output_path=output_path,
                duration_seconds=10.6,
                music_track_id="music_1",
            )

            with self.assertRaises(
                RenderBackendError
            ) as raised:
                backend.render(request)

        message = str(
            raised.exception
        )

        self.assertIn(
            "not yet M114-compatible",
            message,
        )

        self.assertIn(
            "music_track_id",
            message,
        )

        self.assertIn(
            "progress_callback",
            message,
        )

        self.assertIn(
            "cancel_event",
            message,
        )


    def test_successful_render_normalizes_result_and_progress(self):
        renderer = CompatibleRenderer()

        backend = TimelineRendererBackend(
            renderer=renderer
        )

        events = []

        with TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "final_video_001.mp4"
            )

            request = RenderBackendRequest(
                project=object(),
                output_path=output_path,
                duration_seconds=10.6,
                video_track_id="video_1",
                narration_track_id="voice_1",
                music_track_id="music_1",
                mix_policy=RenderMixPolicy(
                    narration_gain_db=0.0,
                    music_gain_db=-24.0,
                    music_fade_in_seconds=1.5,
                    music_fade_out_seconds=2.0,
                    ducking_enabled=True,
                    ducking_reduction_db=6.0,
                    voice_is_primary=True,
                ),
            )

            result = backend.render(
                request,
                progress_callback=events.append,
            )

            self.assertTrue(
                output_path.exists()
            )

        self.assertTrue(
            result.success
        )

        self.assertEqual(
            result.video_clips,
            2,
        )

        self.assertTrue(
            result.has_narration
        )

        self.assertTrue(
            result.has_music
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
            [event.phase for event in events],
            [
                "starting",
                "rendering",
                "completed",
            ],
        )

        self.assertEqual(
            events[-1].percent,
            100.0,
        )

        self.assertEqual(
            len(renderer.calls),
            1,
        )

        call = renderer.calls[0]

        self.assertEqual(
            call["video_track_id"],
            "video_1",
        )

        self.assertEqual(
            call["audio_track_id"],
            "voice_1",
        )

        self.assertEqual(
            call["music_track_id"],
            "music_1",
        )

        self.assertEqual(
            call["mix_policy"][
                "music_gain_db"
            ],
            -24.0,
        )

        self.assertEqual(
            call["mix_policy"][
                "ducking_reduction_db"
            ],
            6.0,
        )


    def test_cancelled_before_render_does_not_invoke_renderer(self):
        renderer = CompatibleRenderer()

        backend = TimelineRendererBackend(
            renderer=renderer
        )

        token = RenderCancellationToken()
        token.cancel()

        with TemporaryDirectory() as directory:
            request = RenderBackendRequest(
                project=object(),
                output_path=(
                    Path(directory)
                    / "cancelled.mp4"
                ),
                duration_seconds=10.6,
            )

            with self.assertRaises(
                RenderBackendCancelled
            ):
                backend.render(
                    request,
                    cancel_token=token,
                )

        self.assertEqual(
            renderer.calls,
            [],
        )


    def test_existing_output_is_rejected_without_overwrite(self):
        renderer = CompatibleRenderer()

        backend = TimelineRendererBackend(
            renderer=renderer
        )

        with TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "existing.mp4"
            )

            output_path.write_bytes(
                b"existing"
            )

            request = RenderBackendRequest(
                project=object(),
                output_path=output_path,
                duration_seconds=10.6,
            )

            with self.assertRaises(
                RenderBackendError
            ):
                backend.render(request)

            self.assertEqual(
                output_path.read_bytes(),
                b"existing",
            )

        self.assertEqual(
            renderer.calls,
            [],
        )


    def test_renderer_exception_is_wrapped(self):
        backend = TimelineRendererBackend(
            renderer=FailingRenderer()
        )

        with TemporaryDirectory() as directory:
            request = RenderBackendRequest(
                project=object(),
                output_path=(
                    Path(directory)
                    / "failure.mp4"
                ),
                duration_seconds=10.6,
            )

            with self.assertRaises(
                RenderBackendError
            ) as raised:
                backend.render(request)

        self.assertIn(
            "synthetic ffmpeg failure",
            str(raised.exception),
        )


    def test_success_without_output_file_is_rejected(self):
        backend = TimelineRendererBackend(
            renderer=MissingOutputRenderer()
        )

        with TemporaryDirectory() as directory:
            request = RenderBackendRequest(
                project=object(),
                output_path=(
                    Path(directory)
                    / "missing.mp4"
                ),
                duration_seconds=10.6,
            )

            with self.assertRaises(
                RenderBackendError
            ) as raised:
                backend.render(request)

        self.assertIn(
            "output file does not exist",
            str(raised.exception),
        )


    def test_renderer_false_success_is_rejected(self):
        backend = TimelineRendererBackend(
            renderer=FalseResultRenderer()
        )

        with TemporaryDirectory() as directory:
            request = RenderBackendRequest(
                project=object(),
                output_path=(
                    Path(directory)
                    / "false.mp4"
                ),
                duration_seconds=10.6,
            )

            with self.assertRaises(
                RenderBackendError
            ) as raised:
                backend.render(request)

        self.assertIn(
            "reported failure",
            str(raised.exception),
        )


if __name__ == "__main__":
    unittest.main()