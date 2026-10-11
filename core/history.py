from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class HistoryEntry:
    operation: str
    data: Dict[str, Any]
    before: Dict[str, Any]
    after: Dict[str, Any]
    revision: int
    author: str = "user"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

    def to_dict(self):
        return asdict(self)


class HistoryManager:

    def __init__(self):
        self.entries: List[HistoryEntry] = []

    def add(self, entry: HistoryEntry):
        self.entries.append(entry)

    def last(self):
        if not self.entries:
            return None

        return self.entries[-1]

    def pop(self):
        if not self.entries:
            return None

        return self.entries.pop()

    def to_dict(self):
        return [
            entry.to_dict()
            for entry in self.entries
        ]