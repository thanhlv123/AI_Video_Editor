from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class SceneContentAnalysis:

    context: str

    subject: str

    action: str

    location: str

    mood: str

    shot: str

    motion: str


    def to_dict(self):

        return asdict(self)


@dataclass
class SceneSearchData:

    primary_keyword: str

    keywords: List[str] = field(
        default_factory=list
    )

    avoid: List[str] = field(
        default_factory=list
    )


    def to_dict(self):

        return asdict(self)


@dataclass
class SceneMediaData:

    preferred_type: str = "video"

    selected: Optional[str] = None


    def to_dict(self):

        return asdict(self)


@dataclass
class SceneAnalysis:

    scene_id: str

    start: float

    end: float

    duration: float

    dialogue: str

    analysis: SceneContentAnalysis

    search: SceneSearchData

    media: SceneMediaData


    def to_dict(self):

        return {
            "scene_id": self.scene_id,

            "start": self.start,

            "end": self.end,

            "duration": self.duration,

            "dialogue": self.dialogue,

            "analysis": (
                self.analysis.to_dict()
            ),

            "search": (
                self.search.to_dict()
            ),

            "media": (
                self.media.to_dict()
            )
        }