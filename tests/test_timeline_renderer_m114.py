from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.media import Media
from core.project import Project
from core.timeline import Clip, Track

from engine.timeline_renderer import (
    TimelineRenderCancelled,
    TimelineRenderError,
    TimelineRenderer,
)


class CapturingTimelineRenderer(TimelineRenderer):
    """
    Test renderer that captures the generated FFmpeg command
    without launching a real FFmpeg process.
    """

    def __init__(self):
        super().__init__(ffmpeg="ffmpeg")
        self.commands = []
        self.run_count = 0

    def _run_ffmpeg(
        self,
        *,
        command,
        duration_seconds,
        progress_callback=None,
        cancel_event=None,
    ):
        self.run_count += 1
        self.commands.append(
            list(command)
        )

        self._check_cancelled(
            cancel_event
        )

        self._emit_progress(
            progress_callback,
            "rendering",
            50.0,
            "Synthetic FFmpeg render.",
        )

        output_path = Path(
            command[-1]
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_bytes(
            b"synthetic-m114-output"
        )


class CancelToken:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def is_cancelled(self):
        return self.cancelled


class TimelineRendererM114Tests(unittest.TestCase):

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


    def _build_project(
        self,
        directory,
        *,
        include_voice=True,
        include_music=True,
        music_source_duration=136.615397,
        music_clip_duration=10.6,
        second_music_clip=False,
    ):
        root = Path(directory)

        video_one = self._touch(
            root / "video_one.mp4"
        )

        video_two = self._touch(
            root / "video_two.mp4"
        )

        voice_path = self._touch(
            root / "voice.wav"
        )

        music_path = self._touch(
            root / "music.mp3"
        )


        project = Project(
            name="M114 Synthetic Project"
        )

        project.settings.width = 1920
        project.settings.height = 1080
        project.settings.fps = 30.0


        project.add_media(
            Media(
                id="video_one",
                path=str(video_one),
                media_type="video",
                name="Video One",
                duration=27.8278,
                width=1920,
                height=1080,
                fps=30.0,
                has_audio=True,
            )
        )

        project.add_media(
            Media(
                id="video_two",
                path=str(video_two),
                media_type="video",
                name="Video Two",
                duration=14.356667,
                width=2048,
                height=1080,
                fps=30.0,
                has_audio=True,
            )
        )

        project.add_media(
            Media(
                id="voice_main",
                path=str(voice_path),
                media_type="audio",
                name="Narration",
                duration=10.6,
                has_audio=True,
            )
        )

        project.add_media(
            Media(
                id="music_main",
                path=str(music_path),
                media_type="audio",
                name="Music",
                duration=music_source_duration,
                has_audio=True,
            )
        )


        video_track = Track(
            id="video_1",
            name="Video 1",
            track_type="video",
        )

        voice_track = Track(
            id="voice_1",
            name="Voice",
            track_type="audio",
        )

        music_track = Track(
            id="music_1",
            name="Music",
            track_type="audio",
        )


        video_track.add_clip(
            Clip(
                id="visual_0001",
                media_id="video_one",
                track_id="video_1",
                start=0.0,
                duration=6.4,
                source_start=0.0,
            )
        )

        video_track.add_clip(
            Clip(
                id="visual_0002",
                media_id="video_two",
                track_id="video_1",
                start=6.4,
                duration=4.2,
                source_start=0.0,
            )
        )


        if include_voice:

            voice_track.add_clip(
                Clip(
                    id="narration_main",
                    media_id="voice_main",
                    track_id="voice_1",
                    start=0.0,
                    duration=10.6,
                    source_start=0.0,
                )
            )


        if include_music:

            music_track.add_clip(
                Clip(
                    id="music_main_clip",
                    media_id="music_main",
                    track_id="music_1",
                    start=0.0,
                    duration=music_clip_duration,
                    source_start=0.0,
                )
            )


            if second_music_clip:

                music_track.add_clip(
                    Clip(
                        id="music_second_clip",
                        media_id="music_main",
                        track_id="music_1",
                        start=5.0,
                        duration=5.0,
                        source_start=0.0,
                    )
                )


        project.timeline.add_track(
            video_track
        )

        project.timeline.add_track(
            voice_track
        )

        project.timeline.add_track(
            music_track
        )


        return project


    def _filter_complex(
        self,
        command,
    ):
        index = command.index(
            "-filter_complex"
        )

        return command[
            index + 1
        ]


    def test_voice_and_music_build_expected_m114_mix(self):
        renderer = CapturingTimelineRenderer()

        progress = []

        def on_progress(
            phase,
            percent,
            detail,
        ):
            progress.append(
                (
                    phase,
                    percent,
                    detail,
                )
            )


        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory
            )

            output_path = (
                Path(directory)
                / "final_video_001.mp4"
            )

            result = renderer.render(
                project=project,
                output_path=output_path,
                video_track_id="video_1",
                audio_track_id="voice_1",
                music_track_id="music_1",
                mix_policy={
                    "narration_gain_db": 0.0,
                    "music_gain_db": -24.0,
                    "music_fade_in_seconds": 1.5,
                    "music_fade_out_seconds": 2.0,
                    "ducking_enabled": True,
                    "ducking_reduction_db": 6.0,
                    "voice_is_primary": True,
                },
                progress_callback=on_progress,
            )


            self.assertTrue(
                output_path.exists()
            )


        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["video_clips"],
            2,
        )

        self.assertTrue(
            result["has_audio"]
        )

        self.assertTrue(
            result["has_narration"]
        )

        self.assertTrue(
            result["has_music"]
        )

        self.assertEqual(
            result["duration_seconds"],
            10.6,
        )

        self.assertEqual(
            renderer.run_count,
            1,
        )


        command = renderer.commands[0]

        filters = self._filter_complex(
            command
        )


        self.assertIn(
            "concat=n=2:v=1:a=0[vout]",
            filters,
        )

        self.assertIn(
            "[2:a]atrim=start=0:duration=10.6",
            filters,
        )

        self.assertIn(
            "[3:a]atrim=start=0:duration=10.6",
            filters,
        )

        self.assertIn(
            "volume=-24dB",
            filters,
        )

        self.assertIn(
            "afade=t=in:st=0:d=1.5",
            filters,
        )

        self.assertIn(
            "afade=t=out:st=8.6:d=2",
            filters,
        )

        self.assertIn(
            "volume=-6dB:",
            filters,
        )

        self.assertIn(
            "between(t\\,0\\,10.6)",
            filters,
        )

        self.assertIn(
            "[anarr][amusic]amix=inputs=2:",
            filters,
        )

        self.assertIn(
            "normalize=0",
            filters,
        )

        self.assertIn(
            "atrim=duration=10.6",
            filters,
        )


        self.assertIn(
            "-progress",
            command,
        )

        progress_index = command.index(
            "-progress"
        )

        self.assertEqual(
            command[
                progress_index + 1
            ],
            "pipe:1",
        )


        phases = [
            item[0]
            for item in progress
        ]

        self.assertEqual(
            phases,
            [
                "preparing",
                "rendering",
                "rendering",
                "finalizing",
            ],
        )


    def test_legacy_voice_only_call_remains_supported(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory,
                include_music=False,
            )

            output_path = (
                Path(directory)
                / "voice_only.mp4"
            )

            result = renderer.render(
                project=project,
                output_path=output_path,
                video_track_id="video_1",
                audio_track_id="voice_1",
            )


        command = renderer.commands[0]

        filters = self._filter_complex(
            command
        )


        self.assertTrue(
            result["has_audio"]
        )

        self.assertTrue(
            result["has_narration"]
        )

        self.assertFalse(
            result["has_music"]
        )

        self.assertIn(
            "[anarr]atrim=duration=10.6",
            filters,
        )

        self.assertNotIn(
            "amix=inputs=2",
            filters,
        )

        self.assertNotIn(
            "amusic",
            filters,
        )


    def test_music_only_render_is_supported(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory,
                include_voice=False,
                include_music=True,
            )

            output_path = (
                Path(directory)
                / "music_only.mp4"
            )

            result = renderer.render(
                project=project,
                output_path=output_path,
                video_track_id="video_1",
                audio_track_id="voice_1",
                music_track_id="music_1",
                mix_policy={
                    "music_gain_db": -20.0,
                    "music_fade_in_seconds": 1.0,
                    "music_fade_out_seconds": 1.0,
                },
            )


        filters = self._filter_complex(
            renderer.commands[0]
        )


        self.assertFalse(
            result["has_audio"]
        )

        self.assertFalse(
            result["has_narration"]
        )

        self.assertTrue(
            result["has_music"]
        )

        self.assertIn(
            "volume=-20dB",
            filters,
        )

        self.assertIn(
            "[amusic]atrim=duration=10.6",
            filters,
        )

        self.assertNotIn(
            "amix=inputs=2",
            filters,
        )


    def test_music_is_stream_looped_when_source_is_too_short(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory,
                include_music=True,
                music_source_duration=2.0,
                music_clip_duration=10.6,
            )

            output_path = (
                Path(directory)
                / "looped_music.mp4"
            )

            renderer.render(
                project=project,
                output_path=output_path,
                music_track_id="music_1",
            )


        command = renderer.commands[0]


        self.assertIn(
            "-stream_loop",
            command,
        )

        loop_index = command.index(
            "-stream_loop"
        )

        self.assertEqual(
            command[
                loop_index + 1
            ],
            "-1",
        )


    def test_music_is_not_stream_looped_when_source_is_long_enough(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory,
                include_music=True,
                music_source_duration=136.0,
                music_clip_duration=10.6,
            )

            renderer.render(
                project=project,
                output_path=(
                    Path(directory)
                    / "normal_music.mp4"
                ),
                music_track_id="music_1",
            )


        command = renderer.commands[0]

        self.assertNotIn(
            "-stream_loop",
            command,
        )


    def test_missing_music_track_is_rejected(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory
            )

            with self.assertRaises(
                TimelineRenderError
            ) as raised:

                renderer.render(
                    project=project,
                    output_path=(
                        Path(directory)
                        / "missing_music.mp4"
                    ),
                    music_track_id="does_not_exist",
                )


        self.assertIn(
            "Music track not found",
            str(raised.exception),
        )

        self.assertEqual(
            renderer.run_count,
            0,
        )


    def test_multiple_music_clips_are_rejected(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory,
                second_music_clip=True,
            )

            with self.assertRaises(
                TimelineRenderError
            ) as raised:

                renderer.render(
                    project=project,
                    output_path=(
                        Path(directory)
                        / "multiple_music.mp4"
                    ),
                    music_track_id="music_1",
                )


        self.assertIn(
            "only one clip",
            str(raised.exception),
        )

        self.assertEqual(
            renderer.run_count,
            0,
        )


    def test_invalid_mix_policy_is_rejected_before_ffmpeg(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory
            )

            with self.assertRaises(
                TimelineRenderError
            ):

                renderer.render(
                    project=project,
                    output_path=(
                        Path(directory)
                        / "bad_mix.mp4"
                    ),
                    music_track_id="music_1",
                    mix_policy={
                        "music_fade_in_seconds": -1.0,
                    },
                )


        self.assertEqual(
            renderer.run_count,
            0,
        )


    def test_cancelled_before_render_never_runs_ffmpeg(self):
        renderer = CapturingTimelineRenderer()

        token = CancelToken(
            cancelled=True
        )

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory
            )

            with self.assertRaises(
                TimelineRenderCancelled
            ):

                renderer.render(
                    project=project,
                    output_path=(
                        Path(directory)
                        / "cancelled.mp4"
                    ),
                    music_track_id="music_1",
                    cancel_event=token,
                )


        self.assertEqual(
            renderer.run_count,
            0,
        )


    def test_video_gap_is_still_rejected(self):
        renderer = CapturingTimelineRenderer()

        with TemporaryDirectory() as directory:

            project = self._build_project(
                directory
            )

            video_track = (
                project.timeline.get_track(
                    "video_1"
                )
            )

            video_track.clips[1].start = 7.0


            with self.assertRaises(
                TimelineRenderError
            ) as raised:

                renderer.render(
                    project=project,
                    output_path=(
                        Path(directory)
                        / "gap.mp4"
                    ),
                    music_track_id="music_1",
                )


        self.assertIn(
            "Timeline gap detected",
            str(raised.exception),
        )

        self.assertEqual(
            renderer.run_count,
            0,
        )


if __name__ == "__main__":
    unittest.main()