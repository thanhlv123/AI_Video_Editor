"""Conservative normalization; never interpret prose or Markdown."""
import re
import unicodedata


class IngestError(ValueError):
    def __init__(self, code, *, scene_id=None, span_start=None, span_end=None):
        self.code = code
        self.scene_id = scene_id
        self.span_start = span_start
        self.span_end = span_end
        super().__init__(code)


def normalize_text(text: str) -> str:
    text = text.removeprefix("\ufeff")
    if any((unicodedata.category(c) == "Cc" and c not in "\t\r\n")
           or unicodedata.category(c) == "Cs" for c in text):
        raise IngestError("invalid_control_character")
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).rstrip("\n")


def normalize_language(language: str | None) -> str | None:
    if language is None:
        return None
    value = language.strip().replace("_", "-").lower()
    if not re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*", value):
        raise IngestError("invalid_language")
    return value
