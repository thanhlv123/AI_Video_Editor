"""M105 project-local storage and voice asset library helpers.

This module intentionally has no PyQt dependency.  It defines filesystem layout
and durable sidecar metadata for user-visible project assets.  ProjectManifest
remains the authority for the *active* voice; this catalog preserves all created
or imported voice files without overwriting them.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_MANIFEST_FILENAME = "project_manifest.json"
ASSETS_DIRNAME = "assets"
VOICE_ASSETS_DIRNAME = "voice"
VOICE_GENERATED_DIRNAME = "generated"
VOICE_IMPORTED_DIRNAME = "imported"
IMAGE_ASSETS_DIRNAME = "images"
VIDEO_ASSETS_DIRNAME = "videos"
MEDIA_IMPORTED_DIRNAME = "imported"
MEDIA_DOWNLOADED_DIRNAME = "downloaded"
MEDIA_GENERATED_DIRNAME = "generated"
MEDIA_ASSET_META_SUFFIX = ".asset.json"
SUPPORTED_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"})
SUPPORTED_VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"})
WORK_DIRNAME = "work"
VOICE_WORK_DIRNAME = "voice"
SCRIPTS_DIRNAME = "scripts"
EXPORTS_DIRNAME = "exports"
CACHE_DIRNAME = "cache"
VOICE_ASSET_META_SUFFIX = ".asset.json"


class ProjectStorageError(RuntimeError):
    """Controlled project-storage failure."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def safe_slug(value: str, fallback: str = "project", max_len: int = 72) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_text).strip("._-")
    return (slug or fallback)[:max_len]


def project_root_from_manifest(manifest_path: Path) -> Path:
    return Path(manifest_path).resolve().parent


def initialize_project_layout(project_root: Path) -> dict[str, Path]:
    root = Path(project_root).resolve()
    directories = {
        "root": root,
        "scripts": root / SCRIPTS_DIRNAME,
        "assets": root / ASSETS_DIRNAME,
        "voice_assets": root / ASSETS_DIRNAME / VOICE_ASSETS_DIRNAME,
        "voice_generated": root / ASSETS_DIRNAME / VOICE_ASSETS_DIRNAME / VOICE_GENERATED_DIRNAME,
        "voice_imported": root / ASSETS_DIRNAME / VOICE_ASSETS_DIRNAME / VOICE_IMPORTED_DIRNAME,
        "image_assets": root / ASSETS_DIRNAME / IMAGE_ASSETS_DIRNAME,
        "image_imported": root / ASSETS_DIRNAME / IMAGE_ASSETS_DIRNAME / MEDIA_IMPORTED_DIRNAME,
        "image_downloaded": root / ASSETS_DIRNAME / IMAGE_ASSETS_DIRNAME / MEDIA_DOWNLOADED_DIRNAME,
        "image_generated": root / ASSETS_DIRNAME / IMAGE_ASSETS_DIRNAME / MEDIA_GENERATED_DIRNAME,
        "video_assets": root / ASSETS_DIRNAME / VIDEO_ASSETS_DIRNAME,
        "video_imported": root / ASSETS_DIRNAME / VIDEO_ASSETS_DIRNAME / MEDIA_IMPORTED_DIRNAME,
        "video_downloaded": root / ASSETS_DIRNAME / VIDEO_ASSETS_DIRNAME / MEDIA_DOWNLOADED_DIRNAME,
        "video_generated": root / ASSETS_DIRNAME / VIDEO_ASSETS_DIRNAME / MEDIA_GENERATED_DIRNAME,
        "work": root / WORK_DIRNAME,
        "voice_work": root / WORK_DIRNAME / VOICE_WORK_DIRNAME,
        "exports": root / EXPORTS_DIRNAME,
        "cache": root / CACHE_DIRNAME,
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories


def create_project_root(parent_dir: Path, project_name: str) -> Path:
    parent = Path(parent_dir).expanduser().resolve()
    if not parent.exists() or not parent.is_dir():
        raise ProjectStorageError(f"Thư mục lưu dự án không tồn tại: {parent}")

    folder_name = safe_slug(project_name, "project")
    project_root = parent / folder_name
    if project_root.exists():
        raise FileExistsError(
            f"Thư mục dự án đã tồn tại: {project_root}. "
            "Hãy đổi tên dự án hoặc chọn nơi lưu khác."
        )

    project_root.mkdir(parents=False, exist_ok=False)
    try:
        initialize_project_layout(project_root)
    except Exception:
        shutil.rmtree(project_root, ignore_errors=True)
        raise
    return project_root


def voice_assets_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_assets"]


def voice_generated_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_generated"]


def voice_imported_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_imported"]


def voice_work_root(project_root: Path) -> Path:
    return initialize_project_layout(project_root)["voice_work"]


def _asset_metadata_path(audio_path: Path) -> Path:
    audio_path = Path(audio_path)
    return audio_path.with_name(audio_path.name + VOICE_ASSET_META_SUFFIX)


def _unique_audio_path(folder: Path, base_name: str, suffix: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    candidate = folder / f"{base_name}{suffix.lower()}"
    index = 2
    while candidate.exists() or _asset_metadata_path(candidate).exists():
        candidate = folder / f"{base_name}_{index:02d}{suffix.lower()}"
        index += 1
    return candidate


@dataclass(frozen=True)
class VoiceAssetRecord:
    asset_id: str
    display_name: str
    kind: str
    path: str
    created_at: str
    provider_id: str | None = None
    model_id: str | None = None
    voice_id: str | None = None
    language: str | None = None
    speed: float | None = None
    duration_seconds: float | None = None
    source_reference: str | None = None
    size_bytes: int | None = None

    @property
    def audio_path(self) -> Path:
        return Path(self.path)

    @property
    def metadata_path(self) -> Path:
        return _asset_metadata_path(self.audio_path)


def new_generated_voice_target(
    project_root: Path,
    *,
    provider_id: str,
    model_id: str | None,
    voice_id: str,
) -> VoiceAssetRecord:
    folder = voice_generated_root(project_root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    asset_id = f"voice_{uuid.uuid4().hex[:12]}"
    parts = [
        stamp,
        safe_slug(provider_id, "tts", 28),
        safe_slug(model_id or "", "", 28),
        safe_slug(voice_id, "voice", 36),
        asset_id[-6:],
    ]
    base = "_".join(part for part in parts if part)
    path = _unique_audio_path(folder, base, ".wav")
    return VoiceAssetRecord(
        asset_id=asset_id,
        display_name=path.stem,
        kind="generated",
        path=str(path),
        created_at=now_iso(),
        provider_id=provider_id or None,
        model_id=model_id or None,
        voice_id=voice_id or None,
    )


def finalize_voice_asset(
    record: VoiceAssetRecord,
    *,
    language: str | None = None,
    speed: float | None = None,
    duration_seconds: float | None = None,
) -> VoiceAssetRecord:
    path = record.audio_path.resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise ProjectStorageError(f"Tệp voice asset không hợp lệ: {path}")

    finalized = VoiceAssetRecord(
        asset_id=record.asset_id,
        display_name=record.display_name,
        kind=record.kind,
        path=str(path),
        created_at=record.created_at,
        provider_id=record.provider_id,
        model_id=record.model_id,
        voice_id=record.voice_id,
        language=language if language is not None else record.language,
        speed=float(speed) if speed is not None else record.speed,
        duration_seconds=(
            float(duration_seconds) if duration_seconds is not None else record.duration_seconds
        ),
        source_reference=record.source_reference,
        size_bytes=int(path.stat().st_size),
    )
    _write_record(finalized)
    return finalized


def import_voice_asset(
    project_root: Path,
    source_path: Path,
    *,
    display_name: str | None = None,
) -> VoiceAssetRecord:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    folder = voice_imported_root(project_root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    asset_id = f"voice_{uuid.uuid4().hex[:12]}"
    label = safe_slug(display_name or source.stem, "imported_voice", 52)
    base = f"{stamp}_{label}_{asset_id[-6:]}"
    target = _unique_audio_path(folder, base, source.suffix or ".wav")
    shutil.copy2(source, target)

    record = VoiceAssetRecord(
        asset_id=asset_id,
        display_name=display_name or source.stem,
        kind="imported",
        path=str(target.resolve()),
        created_at=now_iso(),
        source_reference=str(source),
        size_bytes=int(target.stat().st_size),
    )
    _write_record(record)
    return record


def _write_record(record: VoiceAssetRecord) -> None:
    meta_path = record.metadata_path
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "creator_studio_voice_asset_m105_v1",
        **asdict(record),
    }
    temp = meta_path.with_name(meta_path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(meta_path)


def read_voice_asset_metadata(metadata_path: Path) -> VoiceAssetRecord:
    path = Path(metadata_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProjectStorageError(f"Metadata voice asset không hợp lệ: {path}")
    required = ("asset_id", "display_name", "kind", "path", "created_at")
    if any(not payload.get(key) for key in required):
        raise ProjectStorageError(f"Metadata voice asset thiếu trường bắt buộc: {path}")
    return VoiceAssetRecord(
        asset_id=str(payload["asset_id"]),
        display_name=str(payload["display_name"]),
        kind=str(payload["kind"]),
        path=str(payload["path"]),
        created_at=str(payload["created_at"]),
        provider_id=_optional_str(payload.get("provider_id")),
        model_id=_optional_str(payload.get("model_id")),
        voice_id=_optional_str(payload.get("voice_id")),
        language=_optional_str(payload.get("language")),
        speed=_optional_float(payload.get("speed")),
        duration_seconds=_optional_float(payload.get("duration_seconds")),
        source_reference=_optional_str(payload.get("source_reference")),
        size_bytes=_optional_int(payload.get("size_bytes")),
    )


def _optional_str(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def scan_voice_assets(project_root: Path) -> list[VoiceAssetRecord]:
    root = voice_assets_root(project_root)
    records: list[VoiceAssetRecord] = []
    known_paths: set[Path] = set()

    for metadata_path in sorted(root.rglob(f"*{VOICE_ASSET_META_SUFFIX}")):
        try:
            record = read_voice_asset_metadata(metadata_path)
            audio_path = record.audio_path.resolve()
            if not audio_path.is_file():
                continue
            known_paths.add(audio_path)
            if record.size_bytes != audio_path.stat().st_size:
                record = VoiceAssetRecord(
                    **{**asdict(record), "size_bytes": int(audio_path.stat().st_size)}
                )
            records.append(record)
        except Exception:
            continue

    supported = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
    for audio_path in sorted(root.rglob("*")):
        if not audio_path.is_file() or audio_path.suffix.lower() not in supported:
            continue
        resolved = audio_path.resolve()
        if resolved in known_paths:
            continue
        stat = audio_path.stat()
        records.append(
            VoiceAssetRecord(
                asset_id=f"orphan_{uuid.uuid5(uuid.NAMESPACE_URL, str(resolved)).hex[:12]}",
                display_name=audio_path.stem,
                kind="unindexed",
                path=str(resolved),
                created_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                size_bytes=int(stat.st_size),
            )
        )

    records.sort(key=lambda item: item.created_at, reverse=True)
    return records


def find_voice_asset_by_path(project_root: Path, audio_path: Path) -> VoiceAssetRecord | None:
    wanted = Path(audio_path).resolve()
    for record in scan_voice_assets(project_root):
        try:
            if record.audio_path.resolve() == wanted:
                return record
        except Exception:
            continue
    return None


def create_voice_work_run(project_root: Path, asset_id: str) -> Path:
    root = voice_work_root(project_root) / safe_slug(asset_id, "voice_asset", 64)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    run_dir = root / f"run_{stamp}"
    suffix = 2
    while run_dir.exists():
        run_dir = root / f"run_{stamp}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=False, exist_ok=False)
    return run_dir


# ---------------------------------------------------------------------------
# M106 image/video asset library
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MediaAssetRecord:
    asset_id: str
    display_name: str
    media_type: str
    origin: str
    path: str
    created_at: str
    source_reference: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    size_bytes: int | None = None

    @property
    def media_path(self) -> Path:
        return Path(self.path)

    @property
    def metadata_path(self) -> Path:
        return _media_asset_metadata_path(self.media_path)


def _require_media_type(media_type: str) -> str:
    value = str(media_type or "").strip().lower()
    if value not in {"image", "video"}:
        raise ProjectStorageError(f"Loại media asset không hợp lệ: {media_type}")
    return value


def _require_media_origin(origin: str) -> str:
    value = str(origin or "").strip().lower()
    if value not in {"imported", "downloaded", "generated"}:
        raise ProjectStorageError(f"Nguồn media asset không hợp lệ: {origin}")
    return value


def infer_media_type(path: Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return "image"
    if suffix in SUPPORTED_VIDEO_SUFFIXES:
        return "video"
    raise ProjectStorageError(f"Định dạng ảnh/video chưa được hỗ trợ: {suffix or '(không có đuôi tệp)'}")


def media_assets_root(project_root: Path, media_type: str | None = None) -> Path:
    layout = initialize_project_layout(project_root)
    if media_type is None:
        return layout["assets"]
    media_type = _require_media_type(media_type)
    return layout["image_assets" if media_type == "image" else "video_assets"]


def media_asset_origin_root(project_root: Path, media_type: str, origin: str) -> Path:
    media_type = _require_media_type(media_type)
    origin = _require_media_origin(origin)
    layout = initialize_project_layout(project_root)
    return layout[f"{media_type}_{origin}"]


def _media_asset_metadata_path(media_path: Path) -> Path:
    media_path = Path(media_path)
    return media_path.with_name(media_path.name + MEDIA_ASSET_META_SUFFIX)


def _unique_media_path(folder: Path, base_name: str, suffix: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    candidate = folder / f"{base_name}{suffix.lower()}"
    index = 2
    while candidate.exists() or _media_asset_metadata_path(candidate).exists():
        candidate = folder / f"{base_name}_{index:02d}{suffix.lower()}"
        index += 1
    return candidate


def new_media_asset_target(
    project_root: Path,
    *,
    media_type: str,
    origin: str,
    extension: str,
    display_name: str | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
    source_reference: str | None = None,
) -> MediaAssetRecord:
    media_type = _require_media_type(media_type)
    origin = _require_media_origin(origin)
    extension = str(extension or "").lower()
    if not extension.startswith("."):
        extension = f".{extension}"
    allowed = SUPPORTED_IMAGE_SUFFIXES if media_type == "image" else SUPPORTED_VIDEO_SUFFIXES
    if extension not in allowed:
        raise ProjectStorageError(
            f"Định dạng {extension} không hợp lệ cho {media_type} asset."
        )

    folder = media_asset_origin_root(project_root, media_type, origin)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    asset_id = f"{media_type}_{uuid.uuid4().hex[:12]}"
    label = safe_slug(display_name or media_type, media_type, 52)
    base = f"{stamp}_{label}_{asset_id[-6:]}"
    target = _unique_media_path(folder, base, extension)
    return MediaAssetRecord(
        asset_id=asset_id,
        display_name=display_name or target.stem,
        media_type=media_type,
        origin=origin,
        path=str(target),
        created_at=now_iso(),
        source_reference=source_reference,
        provider_id=provider_id or None,
        model_id=model_id or None,
    )


def finalize_media_asset(
    record: MediaAssetRecord,
    *,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
    duration_seconds: float | None = None,
) -> MediaAssetRecord:
    path = record.media_path.resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise ProjectStorageError(f"Tệp media asset không hợp lệ: {path}")
    detected = infer_media_type(path)
    if detected != record.media_type:
        raise ProjectStorageError(
            f"Tệp {path.name} là {detected}, không khớp metadata {record.media_type}."
        )

    finalized = MediaAssetRecord(
        asset_id=record.asset_id,
        display_name=record.display_name,
        media_type=record.media_type,
        origin=record.origin,
        path=str(path),
        created_at=record.created_at,
        source_reference=record.source_reference,
        provider_id=record.provider_id,
        model_id=record.model_id,
        mime_type=mime_type if mime_type is not None else record.mime_type,
        width=int(width) if width is not None else record.width,
        height=int(height) if height is not None else record.height,
        duration_seconds=(
            float(duration_seconds) if duration_seconds is not None else record.duration_seconds
        ),
        size_bytes=int(path.stat().st_size),
    )
    _write_media_record(finalized)
    return finalized


def import_media_asset(
    project_root: Path,
    source_path: Path,
    *,
    media_type: str | None = None,
    display_name: str | None = None,
) -> MediaAssetRecord:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    detected = infer_media_type(source)
    if media_type is not None and _require_media_type(media_type) != detected:
        raise ProjectStorageError(
            f"Tệp {source.name} không phải loại {media_type} đã chọn."
        )
    media_type = detected
    record = new_media_asset_target(
        project_root,
        media_type=media_type,
        origin="imported",
        extension=source.suffix,
        display_name=display_name or source.stem,
        source_reference=str(source),
    )
    target = record.media_path
    shutil.copy2(source, target)
    return finalize_media_asset(record)


def _write_media_record(record: MediaAssetRecord) -> None:
    meta_path = record.metadata_path
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "creator_studio_media_asset_m106_v1",
        **asdict(record),
    }
    temp = meta_path.with_name(meta_path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(meta_path)


def read_media_asset_metadata(metadata_path: Path) -> MediaAssetRecord:
    path = Path(metadata_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProjectStorageError(f"Metadata media asset không hợp lệ: {path}")
    required = ("asset_id", "display_name", "media_type", "origin", "path", "created_at")
    if any(not payload.get(key) for key in required):
        raise ProjectStorageError(f"Metadata media asset thiếu trường bắt buộc: {path}")
    return MediaAssetRecord(
        asset_id=str(payload["asset_id"]),
        display_name=str(payload["display_name"]),
        media_type=_require_media_type(str(payload["media_type"])),
        origin=_require_media_origin(str(payload["origin"])),
        path=str(payload["path"]),
        created_at=str(payload["created_at"]),
        source_reference=_optional_str(payload.get("source_reference")),
        provider_id=_optional_str(payload.get("provider_id")),
        model_id=_optional_str(payload.get("model_id")),
        mime_type=_optional_str(payload.get("mime_type")),
        width=_optional_int(payload.get("width")),
        height=_optional_int(payload.get("height")),
        duration_seconds=_optional_float(payload.get("duration_seconds")),
        size_bytes=_optional_int(payload.get("size_bytes")),
    )


def scan_media_assets(
    project_root: Path,
    media_type: str | None = None,
) -> list[MediaAssetRecord]:
    if media_type is not None:
        requested = _require_media_type(media_type)
        roots = [media_assets_root(project_root, requested)]
    else:
        roots = [
            media_assets_root(project_root, "image"),
            media_assets_root(project_root, "video"),
        ]

    records: list[MediaAssetRecord] = []
    known_paths: set[Path] = set()
    for root in roots:
        for metadata_path in sorted(root.rglob(f"*{MEDIA_ASSET_META_SUFFIX}")):
            try:
                record = read_media_asset_metadata(metadata_path)
                if media_type is not None and record.media_type != media_type:
                    continue
                media_path = record.media_path.resolve()
                if not media_path.is_file():
                    continue
                known_paths.add(media_path)
                if record.size_bytes != media_path.stat().st_size:
                    record = MediaAssetRecord(
                        **{**asdict(record), "size_bytes": int(media_path.stat().st_size)}
                    )
                records.append(record)
            except Exception:
                continue

    supported = SUPPORTED_IMAGE_SUFFIXES | SUPPORTED_VIDEO_SUFFIXES
    for root in roots:
        for media_path in sorted(root.rglob("*")):
            if not media_path.is_file() or media_path.suffix.lower() not in supported:
                continue
            resolved = media_path.resolve()
            if resolved in known_paths:
                continue
            try:
                detected = infer_media_type(media_path)
                if media_type is not None and detected != media_type:
                    continue
            except Exception:
                continue
            stat = media_path.stat()
            records.append(
                MediaAssetRecord(
                    asset_id=f"orphan_{uuid.uuid5(uuid.NAMESPACE_URL, str(resolved)).hex[:12]}",
                    display_name=media_path.stem,
                    media_type=detected,
                    origin="imported",
                    path=str(resolved),
                    created_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                    size_bytes=int(stat.st_size),
                )
            )

    records.sort(key=lambda item: item.created_at, reverse=True)
    return records


def find_media_asset_by_path(project_root: Path, media_path: Path) -> MediaAssetRecord | None:
    wanted = Path(media_path).resolve()
    for record in scan_media_assets(project_root):
        try:
            if record.media_path.resolve() == wanted:
                return record
        except Exception:
            continue
    return None
