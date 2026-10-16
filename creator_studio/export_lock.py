"""Cross-process export guard for one Creator Studio project.

The lock file is persistent but contains no user media or state. The OS
releases the byte-range/file lock if a process exits unexpectedly.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator


class ProjectExportBusy(RuntimeError):
    """A different export currently owns this project's render slot."""


@contextmanager
def project_export_lock(project_root: Path) -> Iterator[None]:
    """Fail fast if another process or thread is exporting this project.

    The lock is held for the complete export transaction, including
    output-number selection and manifest persistence.
    """
    lock_path = Path(project_root) / "exports" / ".render_export.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+b") as handle:
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            acquired = True
        except OSError as exc:
            raise ProjectExportBusy(
                "Another video export is already running for this project."
            ) from exc

        try:
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
