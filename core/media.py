from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Media:
    """
    Đại diện cho một file media được import vào project.
    """

    id: str
    path: str
    media_type: str

    name: Optional[str] = None
    duration: float = 0.0

    width: Optional[int] = None
    height: Optional[int] = None

    fps: Optional[float] = None

    has_audio: bool = False

    def to_dict(self):
        return asdict(self)