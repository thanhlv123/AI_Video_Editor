import uuid
from pathlib import Path

from core.media import Media
from engine.ffmpeg import FFprobe


class MediaImporter:

    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp"
    }

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
        ".m4v"
    }

    AUDIO_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".aac",
        ".m4a",
        ".flac",
        ".ogg"
    }


    def __init__(self):

        self.probe = FFprobe()


    def detect_media_type(
        self,
        file_path
    ):

        extension = Path(
            file_path
        ).suffix.lower()


        if extension in self.IMAGE_EXTENSIONS:
            return "image"


        if extension in self.VIDEO_EXTENSIONS:
            return "video"


        if extension in self.AUDIO_EXTENSIONS:
            return "audio"


        return "unknown"


    def import_file(
        self,
        file_path,
        media_id=None
    ):

        path = Path(file_path)

        if not path.exists():

            raise FileNotFoundError(
                f"File not found: {file_path}"
            )


        media_type = self.detect_media_type(
            file_path
        )


        if media_type == "unknown":

            raise ValueError(
                f"Unsupported media type: {path.suffix}"
            )


        if media_id is None:

            media_id = (
                "media_"
                + uuid.uuid4().hex[:12]
            )


        information = self.probe.analyze(
            file_path
        )


        return Media(

            id=media_id,

            path=str(path),

            media_type=media_type,

            name=path.name,

            duration=information[
                "duration"
            ],

            width=information[
                "width"
            ],

            height=information[
                "height"
            ],

            fps=information[
                "fps"
            ],

            has_audio=information[
                "has_audio"
            ]
        )