from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Clip:
    """
    Một clip nằm trên timeline.
    """

    id: str
    media_id: str
    track_id: str

    start: float
    duration: float

    source_start: float = 0.0
    source_duration: Optional[float] = None

    enabled: bool = True

    def to_dict(self):
        return asdict(self)

    @property
    def end(self):
        return self.start + self.duration


@dataclass
class Track:
    """
    Một track của timeline.

    Ví dụ:
    video_1
    video_2
    voice
    music
    captions
    """

    id: str
    name: str
    track_type: str

    clips: List[Clip] = field(default_factory=list)

    locked: bool = False
    muted: bool = False
    visible: bool = True

    def add_clip(self, clip: Clip):
        self.clips.append(clip)

    def remove_clip(self, clip_id: str):
        self.clips = [
            clip
            for clip in self.clips
            if clip.id != clip_id
        ]

    def get_clip(self, clip_id: str):
        for clip in self.clips:
            if clip.id == clip_id:
                return clip

        return None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "track_type": self.track_type,
            "locked": self.locked,
            "muted": self.muted,
            "visible": self.visible,
            "clips": [
                clip.to_dict()
                for clip in self.clips
            ]
        }


@dataclass
class Timeline:
    """
    Timeline chính của project.
    """

    tracks: List[Track] = field(default_factory=list)

    def add_track(self, track: Track):
        self.tracks.append(track)

    def get_track(self, track_id: str):
        for track in self.tracks:
            if track.id == track_id:
                return track

        return None

    def get_clip(self, clip_id: str):
        for track in self.tracks:
            clip = track.get_clip(clip_id)

            if clip:
                return clip

        return None

    def to_dict(self):
        return {
            "tracks": [
                track.to_dict()
                for track in self.tracks
            ]
        }