"""UTF-8 atomic persistence with explicit, observable previous-revision recovery."""
import json
import os
from pathlib import Path
import tempfile
from .codec import decode, to_data
from .migrations import migrate_document, UnsupportedSchemaError
from .models import ProjectManifest
from .validation import require_valid


class PersistenceError(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def load(path) -> ProjectManifest:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            document = json.load(stream, object_pairs_hook=_unique_object)
        manifest = decode(ProjectManifest, migrate_document(document))
        require_valid(manifest)
        return manifest
    except UnsupportedSchemaError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise PersistenceError(f"Cannot load manifest ({type(exc).__name__}): {exc}") from exc


def _atomic_write(path: Path, payload: bytes):
    temporary = None
    primary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        except OSError as cleanup:
            if primary is None:
                raise
            primary.add_note(f"Temporary cleanup failed ({type(cleanup).__name__})")


def save(manifest: ProjectManifest, path):
    require_valid(manifest)
    payload = json.dumps(to_data(manifest), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    path = Path(path)
    try:
        # Refuse to overwrite invalid/unsupported destinations; recovery is explicit.
        if path.exists():
            previous = load(path)
            previous_payload = json.dumps(to_data(previous), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
            _atomic_write(path.with_name(path.name + ".bak"), previous_payload)
        _atomic_write(path, payload)
    except OSError as exc:
        raise PersistenceError(f"Cannot save manifest ({type(exc).__name__})") from exc


def recover_previous(path) -> ProjectManifest:
    """Return the validated backup without silently replacing the current file."""
    path = Path(path)
    return load(path.with_name(path.name + ".bak"))
