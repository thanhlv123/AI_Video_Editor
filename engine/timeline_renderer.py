import subprocess
from pathlib import Path


class TimelineRenderError(Exception):
    pass


class TimelineRenderer:

    def __init__(self, ffmpeg="ffmpeg"):
        self.ffmpeg = ffmpeg


    # ==================================================
    # PUBLIC RENDER
    # ==================================================

    def render(
        self,
        project,
        output_path,
        video_track_id="video_1",
        audio_track_id="voice_1"
    ):

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        # ==============================================
        # PROJECT SETTINGS
        # ==============================================

        width = project.settings.width
        height = project.settings.height
        fps = project.settings.fps


        # ==============================================
        # GET TRACKS
        # ==============================================

        video_track = project.timeline.get_track(
            video_track_id
        )

        if video_track is None:
            raise TimelineRenderError(
                f"Video track not found: {video_track_id}"
            )


        audio_track = project.timeline.get_track(
            audio_track_id
        )


        # ==============================================
        # SORT CLIPS
        # ==============================================

        video_clips = sorted(
            video_track.clips,
            key=lambda clip: clip.start
        )


        if not video_clips:
            raise TimelineRenderError(
                "Video track contains no clips."
            )


        # ==============================================
        # VALIDATE VIDEO TIMELINE
        # ==============================================

        self._validate_video_clips(
            video_clips
        )


        # ==============================================
        # BUILD INPUTS
        # ==============================================

        command = [
            self.ffmpeg,
            "-y"
        ]

        video_inputs = []


        for clip in video_clips:

            media = project.get_media(
                clip.media_id
            )

            if media is None:
                raise TimelineRenderError(
                    f"Media not found: {clip.media_id}"
                )


            media_path = Path(
                media.path
            )


            if not media_path.exists():
                raise TimelineRenderError(
                    f"Media file missing: {media_path}"
                )


            input_index = len(
                video_inputs
            )


            if media.media_type == "image":

                command.extend([
                    "-loop",
                    "1",
                    "-framerate",
                    str(fps),
                    "-i",
                    str(media_path)
                ])


            elif media.media_type == "video":

                command.extend([
                    "-i",
                    str(media_path)
                ])


            else:

                raise TimelineRenderError(
                    "Video track can only contain "
                    "image or video media. "
                    f"Found: {media.media_type}"
                )


            video_inputs.append({
                "clip": clip,
                "media": media,
                "input_index": input_index
            })


        # ==============================================
        # AUDIO INPUT
        # ==============================================

        audio_info = None


        if audio_track and audio_track.clips:

            audio_clips = sorted(
                audio_track.clips,
                key=lambda clip: clip.start
            )


            # First version:
            # support one voice clip.
            if len(audio_clips) > 1:

                raise TimelineRenderError(
                    "Current renderer supports only "
                    "one audio clip on the voice track."
                )


            audio_clip = audio_clips[0]


            audio_media = project.get_media(
                audio_clip.media_id
            )


            if audio_media is None:

                raise TimelineRenderError(
                    f"Audio media not found: "
                    f"{audio_clip.media_id}"
                )


            audio_path = Path(
                audio_media.path
            )


            if not audio_path.exists():

                raise TimelineRenderError(
                    f"Audio file missing: "
                    f"{audio_path}"
                )


            audio_input_index = len(
                video_inputs
            )


            command.extend([
                "-i",
                str(audio_path)
            ])


            audio_info = {
                "clip": audio_clip,
                "media": audio_media,
                "input_index": audio_input_index
            }


        # ==============================================
        # BUILD FILTER GRAPH
        # ==============================================

        filters = []

        video_labels = []


        for number, item in enumerate(
            video_inputs
        ):

            clip = item["clip"]
            media = item["media"]
            index = item["input_index"]

            label = f"v{number}"


            if media.media_type == "image":

                filter_part = (
                    f"[{index}:v]"
                    f"scale={width}:{height}:"
                    f"force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:"
                    f"(ow-iw)/2:(oh-ih)/2,"
                    f"setsar=1,"
                    f"fps={fps},"
                    f"trim=duration={clip.duration},"
                    f"setpts=PTS-STARTPTS"
                    f"[{label}]"
                )


            else:

                source_start = clip.source_start

                filter_part = (
                    f"[{index}:v]"
                    f"trim="
                    f"start={source_start}:"
                    f"duration={clip.duration},"
                    f"setpts=PTS-STARTPTS,"
                    f"scale={width}:{height}:"
                    f"force_original_aspect_ratio=increase,"
                    f"crop={width}:{height},"
                    f"setsar=1,"
                    f"fps={fps}"
                    f"[{label}]"
                )


            filters.append(
                filter_part
            )

            video_labels.append(
                f"[{label}]"
            )


        # ==============================================
        # CONCAT VIDEO CLIPS
        # ==============================================

        concat_filter = (
            "".join(video_labels)
            + f"concat=n={len(video_labels)}:"
            + "v=1:a=0[vout]"
        )

        filters.append(
            concat_filter
        )


        # ==============================================
        # AUDIO FILTER
        # ==============================================

        if audio_info:

            audio_clip = audio_info["clip"]
            audio_index = audio_info[
                "input_index"
            ]

            audio_filter = (
                f"[{audio_index}:a]"
                f"atrim="
                f"start={audio_clip.source_start}:"
                f"duration={audio_clip.duration},"
                f"asetpts=PTS-STARTPTS"
                f"[aout]"
            )

            filters.append(
                audio_filter
            )


        filter_complex = ";".join(
            filters
        )


        command.extend([
            "-filter_complex",
            filter_complex,

            "-map",
            "[vout]"
        ])


        if audio_info:

            command.extend([
                "-map",
                "[aout]"
            ])


        # ==============================================
        # OUTPUT SETTINGS
        # ==============================================

        command.extend([
            "-c:v",
            "libx264",

            "-preset",
            "medium",

            "-crf",
            "20",

            "-pix_fmt",
            "yuv420p"
        ])


        if audio_info:

            command.extend([
                "-c:a",
                "aac",

                "-b:a",
                "192k",

                "-ar",
                "48000"
            ])


        command.extend([
            "-movflags",
            "+faststart",

            str(output_path)
        ])


        # ==============================================
        # SHOW RENDER INFORMATION
        # ==============================================

        print()
        print("=" * 70)
        print("TIMELINE RENDER")
        print("=" * 70)

        print(
            "Project:",
            project.name
        )

        print(
            "Resolution:",
            f"{width}x{height}"
        )

        print(
            "FPS:",
            fps
        )

        print(
            "Video clips:",
            len(video_clips)
        )

        print(
            "Audio:",
            "YES" if audio_info else "NO"
        )

        print()

        print("FFMPEG COMMAND")
        print("-" * 70)

        print(
            " ".join(
                f'"{item}"'
                if " " in item
                else item
                for item in command
            )
        )

        print()


        # ==============================================
        # RUN FFMPEG
        # ==============================================

        process = subprocess.run(
            command
        )


        if process.returncode != 0:

            raise TimelineRenderError(
                "FFmpeg timeline render failed."
            )


        if not output_path.exists():

            raise TimelineRenderError(
                "Render completed but output "
                "file was not created."
            )


        return {
            "success": True,
            "output": str(output_path),
            "video_clips": len(video_clips),
            "has_audio": audio_info is not None,
            "width": width,
            "height": height,
            "fps": fps
        }


    # ==================================================
    # VALIDATION
    # ==================================================

    def _validate_video_clips(
        self,
        clips
    ):

        expected_start = 0.0

        tolerance = 0.001


        for clip in clips:

            if clip.duration <= 0:

                raise TimelineRenderError(
                    f"Invalid duration for "
                    f"{clip.id}: {clip.duration}"
                )


            # GAP
            if (
                clip.start
                > expected_start + tolerance
            ):

                raise TimelineRenderError(
                    f"Timeline gap detected before "
                    f"{clip.id}. "
                    f"Expected start: "
                    f"{expected_start}, "
                    f"actual: {clip.start}"
                )


            # OVERLAP
            if (
                clip.start
                < expected_start - tolerance
            ):

                raise TimelineRenderError(
                    f"Timeline overlap detected at "
                    f"{clip.id}. "
                    f"Expected start: "
                    f"{expected_start}, "
                    f"actual: {clip.start}"
                )


            expected_start = (
                clip.start
                + clip.duration
            )