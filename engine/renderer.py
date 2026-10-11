import subprocess
from pathlib import Path


class RenderError(Exception):
    pass


class FFmpegRenderer:

    def __init__(
        self,
        ffmpeg="ffmpeg"
    ):
        self.ffmpeg = ffmpeg


    def render_test_video(
        self,
        image_path,
        video_path,
        voice_path,
        output_path,
        width=1920,
        height=1080,
        fps=30,
        image_duration=5,
        video_duration=10
    ):

        image_path = Path(image_path)
        video_path = Path(video_path)
        voice_path = Path(voice_path)
        output_path = Path(output_path)


        # ----------------------------------------------
        # CHECK FILES
        # ----------------------------------------------

        for path in (
            image_path,
            video_path,
            voice_path
        ):

            if not path.exists():

                raise FileNotFoundError(
                    f"File not found: {path}"
                )


        # ----------------------------------------------
        # CREATE OUTPUT DIRECTORY
        # ----------------------------------------------

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        total_duration = (
            image_duration
            + video_duration
        )


        # ----------------------------------------------
        # VIDEO FILTER
        #
        # IMAGE:
        # scale while preserving aspect ratio
        # then pad to 1920x1080
        #
        # VIDEO:
        # scale to fill frame
        # then crop to 1920x1080
        #
        # Finally concatenate both.
        # ----------------------------------------------

        filter_complex = (

            # IMAGE
            f"[0:v]"
            f"scale={width}:{height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:"
            f"(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,"
            f"fps={fps},"
            f"trim=duration={image_duration},"
            f"setpts=PTS-STARTPTS"
            f"[image];"

            # VIDEO
            f"[1:v]"
            f"trim=start=0:"
            f"duration={video_duration},"
            f"setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"setsar=1,"
            f"fps={fps}"
            f"[video];"

            # CONCAT IMAGE + VIDEO
            f"[image][video]"
            f"concat=n=2:v=1:a=0"
            f"[v]"
        )


        # ----------------------------------------------
        # FFMPEG COMMAND
        # ----------------------------------------------

        command = [

            self.ffmpeg,

            "-y",

            # IMAGE INPUT
            "-loop",
            "1",

            "-framerate",
            str(fps),

            "-i",
            str(image_path),

            # VIDEO INPUT
            "-i",
            str(video_path),

            # VOICE INPUT
            "-i",
            str(voice_path),

            # FILTER
            "-filter_complex",
            filter_complex,

            # VIDEO FROM FILTER
            "-map",
            "[v]",

            # AUDIO FROM VOICE INPUT
            "-map",
            "2:a:0",

            # VIDEO CODEC
            "-c:v",
            "libx264",

            "-preset",
            "medium",

            "-crf",
            "20",

            # PIXEL FORMAT
            "-pix_fmt",
            "yuv420p",

            # AUDIO CODEC
            "-c:a",
            "aac",

            "-b:a",
            "192k",

            # AUDIO SAMPLE RATE
            "-ar",
            "48000",

            # OUTPUT DURATION
            "-t",
            str(total_duration),

            # WEB/STREAMING FRIENDLY
            "-movflags",
            "+faststart",

            str(output_path)
        ]


        # ----------------------------------------------
        # DISPLAY COMMAND
        # ----------------------------------------------

        print()
        print("=" * 70)
        print("FFMPEG RENDER")
        print("=" * 70)

        print()

        print(
            " ".join(
                f'"{item}"'
                if " " in item
                else item
                for item in command
            )
        )

        print()


        # ----------------------------------------------
        # EXECUTE
        # ----------------------------------------------

        process = subprocess.run(
            command
        )


        if process.returncode != 0:

            raise RenderError(
                "FFmpeg render failed."
            )


        # ----------------------------------------------
        # RESULT
        # ----------------------------------------------

        if not output_path.exists():

            raise RenderError(
                "FFmpeg completed but output file was not created."
            )


        return {
            "success": True,

            "output": str(
                output_path
            ),

            "duration": total_duration,

            "width": width,

            "height": height,

            "fps": fps
        }