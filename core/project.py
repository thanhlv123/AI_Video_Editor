import json
from dataclasses import dataclass, field
from typing import List, Optional

from core.media import Media
from core.timeline import Timeline


@dataclass
class ProjectSettings:
    width: int = 1920
    height: int = 1080
    fps: float = 30.0

    def to_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps
        }


@dataclass
class Project:
    """
    Model chính của project AI Video Editor.
    """

    name: str

    version: int = 1
    revision: int = 0

    settings: ProjectSettings = field(
        default_factory=ProjectSettings
    )

    media: List[Media] = field(
        default_factory=list
    )

    timeline: Timeline = field(
        default_factory=Timeline
    )

    def add_media(self, media: Media):
        """
        Thêm media vào project.
        """

        existing = self.get_media(media.id)

        if existing:
            raise ValueError(
                f"Media ID already exists: {media.id}"
            )

        self.media.append(media)

        self.revision += 1

    def get_media(self, media_id: str) -> Optional[Media]:

        for item in self.media:

            if item.id == media_id:
                return item

        return None

    def to_dict(self):

        return {
            "version": self.version,
            "revision": self.revision,

            "project": {
                "name": self.name,
                **self.settings.to_dict()
            },

            "media": [
                item.to_dict()
                for item in self.media
            ],

            "timeline": self.timeline.to_dict()
        }

    def save(self, path: str):

        data = self.to_dict()

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )