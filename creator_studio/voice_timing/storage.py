"""Read-only runtime resolution. Paths never enter retained evidence."""
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, ContextManager, Protocol

class NarrationByteStore(Protocol):
    def open_read(self, asset_id: str) -> ContextManager[BinaryIO]: ...

class LocalNarrationByteStore:
    """Caller supplies logical asset associations; no ownership of file lifecycle."""
    def __init__(self, paths):
        self._paths = {key: Path(value) for key, value in paths.items()}

    @contextmanager
    def open_read(self, asset_id):
        with self._paths[asset_id].open("rb") as stream:
            yield stream
