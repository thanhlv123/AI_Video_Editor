import json
import subprocess
from pathlib import Path


class FFmpegError(Exception):
    pass


class FFprobe:

    def __init__(self, executable="ffprobe"):
        self.executable = executable


    def probe(self, file_path):

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Media file not found: {file_path}"
            )

        command = [
            self.executable,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path)
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            raise FFmpegError(
                result.stderr.strip()
            )

        return json.loads(
            result.stdout
        )


    def analyze(self, file_path):

        data = self.probe(
            file_path
        )

        streams = data.get(
            "streams",
            []
        )

        format_data = data.get(
            "format",
            {}
        )

        video_stream = None
        audio_stream = None

        for stream in streams:

            codec_type = stream.get(
                "codec_type"
            )

            if (
                codec_type == "video"
                and video_stream is None
            ):
                video_stream = stream

            elif (
                codec_type == "audio"
                and audio_stream is None
            ):
                audio_stream = stream


        duration = self._get_duration(
            format_data,
            video_stream,
            audio_stream
        )


        result = {
            "path": str(file_path),
            "duration": duration,
            "has_video": video_stream is not None,
            "has_audio": audio_stream is not None
        }


        if video_stream:

            result.update({
                "width": video_stream.get(
                    "width"
                ),

                "height": video_stream.get(
                    "height"
                ),

                "video_codec": video_stream.get(
                    "codec_name"
                ),

                "fps": self._parse_fps(
                    video_stream.get(
                        "avg_frame_rate"
                    )
                )
            })

        else:

            result.update({
                "width": None,
                "height": None,
                "video_codec": None,
                "fps": None
            })


        if audio_stream:

            result.update({
                "audio_codec": audio_stream.get(
                    "codec_name"
                ),

                "sample_rate": self._to_int(
                    audio_stream.get(
                        "sample_rate"
                    )
                ),

                "channels": audio_stream.get(
                    "channels"
                )
            })

        else:

            result.update({
                "audio_codec": None,
                "sample_rate": None,
                "channels": None
            })


        return result


    def _parse_fps(self, value):

        if not value:
            return None

        try:

            numerator, denominator = value.split(
                "/"
            )

            numerator = float(
                numerator
            )

            denominator = float(
                denominator
            )

            if denominator == 0:
                return None

            return numerator / denominator

        except Exception:
            return None


    def _get_duration(
        self,
        format_data,
        video_stream,
        audio_stream
    ):

        value = format_data.get(
            "duration"
        )

        if value:

            try:
                return float(value)

            except ValueError:
                pass


        for stream in (
            video_stream,
            audio_stream
        ):

            if not stream:
                continue

            value = stream.get(
                "duration"
            )

            if value:

                try:
                    return float(value)

                except ValueError:
                    pass


        return 0.0


    def _to_int(self, value):

        try:
            return int(value)

        except (TypeError, ValueError):
            return None