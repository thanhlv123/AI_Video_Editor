from pathlib import Path

from engine.ffmpeg import (
    FFprobe,
    FFmpegError
)


class MediaValidationError(Exception):
    pass


class MediaValidator:

    def __init__(
        self,
        ffprobe=None
    ):

        self.ffprobe = (
            ffprobe
            or FFprobe()
        )


    # ==================================================
    # VALIDATE
    # ==================================================

    def validate(
        self,
        file_path,
        expected_type=None
    ):

        path = Path(
            file_path
        )


        if not path.exists():

            raise MediaValidationError(
                f"Media file does not exist: "
                f"{path}"
            )


        if not path.is_file():

            raise MediaValidationError(
                f"Media path is not a file: "
                f"{path}"
            )


        if path.stat().st_size <= 0:

            raise MediaValidationError(
                "Media file is empty."
            )


        # ==================================================
        # FFPROBE
        # ==================================================

        try:

            info = self.ffprobe.analyze(
                path
            )

        except (
            FFmpegError,
            Exception
        ) as error:

            raise MediaValidationError(
                f"FFprobe validation failed: "
                f"{error}"
            ) from error


        # ==================================================
        # BASIC DURATION
        # ==================================================

        duration = float(
            info.get(
                "duration",
                0
            )
            or 0
        )


        if duration <= 0:

            raise MediaValidationError(
                "Media duration is invalid."
            )


        # ==================================================
        # EXPECTED VIDEO
        # ==================================================

        if expected_type == "video":

            if not info.get(
                "has_video"
            ):

                raise MediaValidationError(
                    "Expected video, but "
                    "no video stream was found."
                )


            width = info.get(
                "width"
            )

            height = info.get(
                "height"
            )


            if (
                not width
                or
                not height
            ):

                raise MediaValidationError(
                    "Video resolution is invalid."
                )


            if not info.get(
                "video_codec"
            ):

                raise MediaValidationError(
                    "Video codec was not detected."
                )


        # ==================================================
        # EXPECTED AUDIO
        # ==================================================

        elif expected_type == "audio":

            if not info.get(
                "has_audio"
            ):

                raise MediaValidationError(
                    "Expected audio, but "
                    "no audio stream was found."
                )


            if not info.get(
                "audio_codec"
            ):

                raise MediaValidationError(
                    "Audio codec was not detected."
                )


        # ==================================================
        # EXPECTED IMAGE
        # ==================================================

        elif expected_type == "image":

            if not info.get(
                "has_video"
            ):

                raise MediaValidationError(
                    "Expected image, but "
                    "no visual stream was found."
                )


            if (
                not info.get("width")
                or
                not info.get("height")
            ):

                raise MediaValidationError(
                    "Image dimensions are invalid."
                )


        # ==================================================
        # SUCCESS
        # ==================================================

        return {

            "valid": True,

            "path": str(
                path.resolve()
            ),

            "size": (
                path.stat().st_size
            ),

            "duration": duration,

            "has_video": info.get(
                "has_video"
            ),

            "has_audio": info.get(
                "has_audio"
            ),

            "width": info.get(
                "width"
            ),

            "height": info.get(
                "height"
            ),

            "video_codec": info.get(
                "video_codec"
            ),

            "fps": info.get(
                "fps"
            ),

            "audio_codec": info.get(
                "audio_codec"
            ),

            "sample_rate": info.get(
                "sample_rate"
            ),

            "channels": info.get(
                "channels"
            )
        }