"""Read-only bounded UTF-8 readers. No format detection or encoding guessing."""
from pathlib import Path
from .models import IngestRequest, IngestLimits, SourceType
from .normalization import IngestError


def read_text(request: IngestRequest, limits: IngestLimits) -> str:
    if request.source_type not in {SourceType.DIRECT_TEXT, SourceType.TEXT_FILE,
                                   SourceType.MARKDOWN, SourceType.REFERENCE_TEXT}:
        raise IngestError("unsupported_source_type")
    if request.text is not None:
        if request.source_type == SourceType.TEXT_FILE or request.source_locator is not None:
            raise IngestError("ambiguous_source")
        text = request.text
        if len(text) > limits.max_characters:
            raise IngestError("content_too_large")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError:
            raise IngestError("invalid_control_character") from None
        if size > limits.max_bytes:
            raise IngestError("content_too_large")
        return text
    if request.source_type not in {SourceType.TEXT_FILE, SourceType.MARKDOWN}:
        raise IngestError("source_required")
    if not request.source_locator:
        raise IngestError("source_required")
    try:
        path = Path(request.source_locator)
        if not path.exists():
            raise IngestError("source_not_found")
        if path.is_dir():
            raise IngestError("source_is_directory")
        if not path.is_file():
            raise IngestError("unsupported_file_type")
        allowed = {".txt"} if request.source_type == SourceType.TEXT_FILE else {".md", ".markdown"}
        if path.suffix.lower() not in allowed:
            raise IngestError("unsupported_file_type")
        with path.open("rb") as stream:
            payload = stream.read(limits.max_bytes + 1)
        if len(payload) > limits.max_bytes:
            raise IngestError("content_too_large")
        return payload.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise IngestError("invalid_utf8") from None
    except (OSError, ValueError) as exc:
        if isinstance(exc, IngestError):
            raise
        raise IngestError("source_read_failed") from None
