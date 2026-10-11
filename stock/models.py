from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class StockMedia:

    provider: str
    media_id: str
    media_type: str

    title: str

    width: Optional[int]
    height: Optional[int]

    duration: Optional[float]

    preview_url: Optional[str]
    thumbnail_url: Optional[str]
    download_url: Optional[str]

    source_url: Optional[str]

    photographer: Optional[str] = None

    score: float = 0.0


    def to_dict(self):

        return asdict(self)